/// Durable storage for cleans: manifests plus the photo bytes themselves.
///
/// All the logic lives here, pure over an injected [SessionFiles], so it is
/// fully testable with no platform binding. Photo bytes becoming durable is
/// the point: before this, a capture lived in a local variable until the
/// upload succeeded, so any failure lost the shot with nothing to retry.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/services/session_files.dart';

/// How much room the app's photos may take on the phone.
///
/// Generous on purpose: photos per clean are unbounded by design, and the
/// point of keeping them is being able to look at them later. At roughly
/// 200 KB a shot this is thousands of photos before anything is freed.
const int kPhotoStorageBudgetBytes = 1500 * 1024 * 1024;

/// Reads and writes [CleanSession]s.
class SessionStore {
  /// Creates a store over [files].
  SessionStore(this.files);

  /// The backing storage.
  final SessionFiles files;

  /// Every stored session, newest first.
  Future<List<CleanSession>> load() async {
    final text = await files.readIndex();
    if (text == null || text.isEmpty) return [];
    Object? decoded;
    try {
      decoded = jsonDecode(text);
    } on FormatException {
      // A corrupt index must not brick the app; the photos are still on
      // disk and a later save rebuilds it.
      return [];
    }
    if (decoded is! List) return [];
    final sessions = decoded
        .map(CleanSession.fromJson)
        .whereType<CleanSession>()
        .toList()
      ..sort((a, b) => b.capturedAt.compareTo(a.capturedAt));
    return sessions;
  }

  Future<void> _save(List<CleanSession> sessions) async {
    await files.writeIndex(
      jsonEncode(sessions.map((s) => s.toJson()).toList()),
    );
  }

  /// Inserts or replaces [session].
  Future<void> put(CleanSession session) async {
    final sessions = await load()
      ..removeWhere((s) => s.id == session.id)
      ..add(session);
    await _save(sessions);
  }

  /// Appends a photo to [session] and returns the updated session.
  ///
  /// The bytes are written before the manifest, so a crash between the two
  /// leaves an unreferenced file rather than a manifest pointing at nothing.
  ///
  /// The name is derived from a counter that never reuses an index, even
  /// after a photo is pruned, so appending to an old clean cannot overwrite
  /// a surviving file.
  Future<CleanSession> addPhoto(CleanSession session, Uint8List bytes) async {
    final name = '${session.id}-${_nextIndex(session)}.jpg';
    await files.writePhoto(name, bytes);
    final updated = session.copyWith(
      photos: [
        ...session.photos,
        SessionPhoto(name: name, bytes: bytes.length),
      ],
    );
    await put(updated);
    return updated;
  }

  static String _nextIndex(CleanSession session) {
    var highest = -1;
    for (final photo in session.photos) {
      final digits = photo.name.split('-').last.split('.').first;
      final parsed = int.tryParse(digits);
      if (parsed != null && parsed > highest) highest = parsed;
    }
    return (highest + 1).toString().padLeft(2, '0');
  }

  /// Total bytes every stored photo occupies.
  Future<int> totalBytes() async {
    final sessions = await load();
    return sessions.fold<int>(0, (sum, s) => sum + s.totalBytes);
  }

  /// Reads one photo's bytes.
  Future<Uint8List?> photo(String name) => files.readPhoto(name);

  /// Sessions waiting to reach the PC, oldest first.
  Future<List<CleanSession>> queued() async {
    final all = await load();
    return all.where((s) => s.status == SessionStatus.queued).toList().reversed
        .toList();
  }

  /// Deletes a session and its photos.
  Future<void> remove(String id) async {
    final sessions = await load();
    for (final session in sessions.where((s) => s.id == id)) {
      for (final name in session.photoNames) {
        await files.deletePhoto(name);
      }
    }
    await _save(sessions.where((s) => s.id != id).toList());
  }

  /// Frees photo files until total storage fits [budgetBytes].
  ///
  /// Budget-driven rather than age-driven: the point of keeping photos is
  /// being able to look at them later, and a fixed 30-day window silently
  /// breaks exactly that, one month after you start relying on it. Oldest
  /// accepted cleans are freed first, and the manifest is kept so the record
  /// of the clean survives its images.
  ///
  /// Never touches a session that has not reached the PC. Discarding
  /// un-credited work is the failure this store exists to prevent, so an
  /// unsynced clean is never freed no matter how tight storage is.
  Future<void> prune({required int budgetBytes}) async {
    final sessions = await load();
    var total = sessions.fold<int>(0, (sum, s) => sum + s.totalBytes);
    if (total <= budgetBytes) return;

    // Oldest first: the most recent cleans are the ones worth looking at.
    final candidates = sessions.reversed
        .where((s) => s.status == SessionStatus.accepted && s.photos.isNotEmpty)
        .toList();

    final freed = <String>{};
    for (final session in candidates) {
      if (total <= budgetBytes) break;
      for (final photo in session.photos) {
        await files.deletePhoto(photo.name);
        total -= photo.bytes;
      }
      freed.add(session.id);
    }
    if (freed.isEmpty) return;
    await _save([
      for (final s in sessions)
        if (freed.contains(s.id)) s.copyWith(photos: []) else s,
    ]);
  }
}
