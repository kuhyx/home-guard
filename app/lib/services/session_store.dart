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
  Future<CleanSession> addPhoto(CleanSession session, Uint8List bytes) async {
    final index = session.photoCount.toString().padLeft(2, '0');
    final name = '${session.id}-$index.jpg';
    await files.writePhoto(name, bytes);
    final updated = session.copyWith(photoNames: [...session.photoNames, name]);
    await put(updated);
    return updated;
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

  /// Deletes photo files for accepted sessions older than [keepDays],
  /// keeping the manifest so the history still shows the clean happened.
  ///
  /// Never touches a queued session: that would discard un-credited work,
  /// which is the exact failure this store exists to prevent.
  Future<void> prune({required String today, int keepDays = 30}) async {
    final sessions = await load();
    final cutoff = _minusDays(today, keepDays);
    var changed = false;
    final kept = <CleanSession>[];
    for (final session in sessions) {
      if (session.status == SessionStatus.accepted &&
          session.day.compareTo(cutoff) < 0 &&
          session.photoNames.isNotEmpty) {
        for (final name in session.photoNames) {
          await files.deletePhoto(name);
        }
        kept.add(session.copyWith(photoNames: []));
        changed = true;
      } else {
        kept.add(session);
      }
    }
    if (changed) await _save(kept);
  }

  static String _minusDays(String day, int days) {
    final parsed = DateTime.parse(day).subtract(Duration(days: days));
    final m = parsed.month.toString().padLeft(2, '0');
    final d = parsed.day.toString().padLeft(2, '0');
    return '${parsed.year}-$m-$d';
  }
}
