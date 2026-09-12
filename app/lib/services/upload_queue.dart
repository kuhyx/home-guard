/// Sends queued cleans to the PC when it becomes reachable.
///
/// A session captured offline has no token -- the PC mints those, and it was
/// not there. So on drain the queue binds the session to whatever challenge
/// is published *now*, which is the only way a clean done with the PC off can
/// ever be credited.
///
/// It binds **same-day sessions only**. Attaching yesterday's cleaning to
/// today's challenge would consume today's single-use token for work that
/// lands in yesterday's log bucket, leaving today both uncredited and
/// unclearable. An older session is kept as an honest record instead of
/// being silently dropped along with the work it represents.
library;

import 'dart:typed_data';

import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';
import 'package:home_guard_app/services/session_store.dart';

/// What one drain attempt did.
class DrainReport {
  /// Creates a report.
  const DrainReport({this.uploaded = 0, this.stillQueued = 0, this.kept = 0});

  /// Sessions the PC accepted.
  final int uploaded;

  /// Sessions still waiting (no signal, or no challenge published).
  final int stillQueued;

  /// Sessions kept as a record because they can no longer be credited.
  final int kept;
}

/// Drains queued sessions.
class UploadQueue {
  /// Creates a queue.
  UploadQueue({
    required this.store,
    required this.sync,
    required this.deviceId,
    DateTime Function()? clock,
    EncodedPhoto Function(Uint8List raw)? encode,
  }) : _clock = clock ?? DateTime.now,
       _encode = encode ?? encodePhotoUnderCap;

  /// Durable session storage.
  final SessionStore store;

  /// The transport.
  final ChallengeSync sync;

  /// This install's id.
  final String deviceId;

  final DateTime Function() _clock;
  final EncodedPhoto Function(Uint8List) _encode;

  /// Tries to send every queued session. Never throws.
  Future<DrainReport> drain() async {
    final queued = await store.queued();
    if (queued.isEmpty) return const DrainReport();

    final read = await sync.fetchChallenge();
    final challenge = read.challenge;
    final today = Challenge.dayOf(_clock());

    var uploaded = 0;
    var waiting = 0;
    var kept = 0;
    for (final session in queued) {
      if (session.day != today) {
        await store.put(
          session.copyWith(
            status: SessionStatus.rejected,
            detail:
                'Kept as a record — the PC was not running on the day this '
                'was cleaned, so it could not be credited.',
          ),
        );
        kept++;
        continue;
      }
      if (challenge == null || !challenge.isSatisfiable(_clock())) {
        waiting++;
        continue;
      }
      final sent = await _send(session, challenge);
      if (sent) {
        uploaded++;
      } else {
        waiting++;
      }
    }
    return DrainReport(uploaded: uploaded, stillQueued: waiting, kept: kept);
  }

  Future<bool> _send(CleanSession session, Challenge challenge) async {
    final photos = <EncodedPhoto>[];
    for (final name in session.photoNames) {
      final bytes = await store.photo(name);
      // A missing file means the manifest outlived its photos. Skip it
      // rather than aborting: some evidence beats none, and the PC caps
      // each photo anyway.
      if (bytes == null) continue;
      try {
        photos.add(_encode(bytes));
      } on Exception {
        continue;
      }
    }
    if (photos.isEmpty) return false;

    final result = await sync.uploadEvidence(
      challenge: challenge,
      photos: photos,
      deviceId: deviceId,
      zone: session.zone,
      capturedAt: DateTime.tryParse(session.capturedAt),
    );
    if (result.outcome != SyncOutcome.ok) return false;
    await store.put(session.copyWith(status: SessionStatus.accepted));
    return true;
  }
}
