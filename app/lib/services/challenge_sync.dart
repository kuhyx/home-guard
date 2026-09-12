/// The phone's half of the publish-then-echo protocol.
///
/// Reads the PC's challenge, uploads the evidence with the token echoed
/// verbatim, and watches for the PC to drain the evidence node (its only
/// "accepted" signal). The phone never deletes anything: a rejected payload
/// is left where the PC left it, so a legitimate retry simply overwrites it.
/// See `docs/DOCS-marker-protocol.md`.
library;

import 'dart:convert';
import 'dart:developer' as developer;

import 'package:crdt_sync/crdt_sync.dart';
import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/services/firebase_backend.dart';
import 'package:home_guard_app/services/photo_encoder.dart';

/// RTDB paths, identical to `home_guard/_constants.py`. Logical paths with
/// the `.json` suffix intact: both clients escape `.` the same way.
const kChallengePath = 'home-guard-sync/challenge/current.json';

/// Where the phone writes and the PC drains.
const kEvidencePath = 'home-guard-sync/evidence/current.json';

/// Outcome of a read or write, for the screen to render.
enum SyncOutcome {
  /// Firebase is not configured on this device.
  notConfigured,

  /// The call failed (network, auth, malformed payload).
  error,

  /// Nothing published (or unparsable) -- the PC has no slot due.
  noChallenge,

  /// Success.
  ok,
}

/// A challenge read.
class ChallengeRead {
  /// Creates a read result.
  const ChallengeRead(this.outcome, {this.challenge, this.detail = ''});

  /// What happened.
  final SyncOutcome outcome;

  /// The parsed challenge, only on [SyncOutcome.ok].
  final Challenge? challenge;

  /// Human-readable reason for a non-ok outcome.
  final String detail;
}

/// Firebase reads/writes for the challenge and evidence nodes.
class ChallengeSync {
  /// Creates a syncer; [openClient] and [clock] are injectable for tests.
  ChallengeSync({
    Future<RemoteStore?> Function()? openClient,
    DateTime Function()? clock,
  }) : _openClient = openClient ?? openFirebase,
       _clock = clock ?? DateTime.now;

  final Future<RemoteStore?> Function() _openClient;
  final DateTime Function() _clock;

  /// Fetches the current challenge. Never throws.
  Future<ChallengeRead> fetchChallenge() async {
    final client = await _open();
    if (client == null) {
      return const ChallengeRead(
        SyncOutcome.notConfigured,
        detail: 'Not synced — connect Firebase in Settings.',
      );
    }
    try {
      final text = await client.getFileText(kChallengePath);
      if (text == null) return const ChallengeRead(SyncOutcome.noChallenge);
      final challenge = Challenge.fromJson(jsonDecode(text));
      if (challenge == null) {
        return const ChallengeRead(
          SyncOutcome.noChallenge,
          detail: 'The PC has published nothing readable yet.',
        );
      }
      return ChallengeRead(SyncOutcome.ok, challenge: challenge);
    } on Exception catch (e) {
      return ChallengeRead(SyncOutcome.error, detail: 'Error: $e');
    }
  }

  /// Uploads [photos] as evidence for [challenge]. Never throws.
  ///
  /// `day`/`slot`/`token` are copied from [challenge] untouched -- the PC's
  /// verifier compares them by exact equality. `zone` is whatever was
  /// actually cleaned, which need not be the zone the challenge names: the
  /// PC checks it for membership of the rotation, so five photos of a mirror
  /// are not thrown away because the cursor pointed at the desk.
  ///
  /// [capturedAt] is when the photos were TAKEN, which for a session queued
  /// offline is not now. The PC files the clear entry under that day, so a
  /// clean done today unlocks today and one done yesterday keeps its record
  /// without granting anything now.
  ///
  /// Returns [SyncOutcome.ok] once the write is durable; acceptance is a
  /// separate question answered by [evidenceDrained].
  Future<ChallengeRead> uploadEvidence({
    required Challenge challenge,
    required List<EncodedPhoto> photos,
    required String deviceId,
    String? zone,
    DateTime? capturedAt,
  }) async {
    final client = await _open();
    if (client == null) {
      return const ChallengeRead(
        SyncOutcome.notConfigured,
        detail: 'Not synced — connect Firebase in Settings.',
      );
    }
    final taken = (capturedAt ?? _clock()).toUtc();
    final payload = <String, Object?>{
      'day': challenge.day,
      'slot': challenge.slot,
      'zone': zone ?? challenge.zone,
      'token': challenge.token,
      'device_id': deviceId,
      'captured_at': taken.toIso8601String(),
      'captured_day': Challenge.dayOf(taken),
      'photos': [
        for (final p in photos) {'b64': p.base64, 'mime': 'image/jpeg'},
      ],
    };
    try {
      await client.putFileText(
        kEvidencePath,
        jsonEncode(payload),
        message:
            'home-guard: ${photos.length} photo(s) for '
            '${challenge.day} ${challenge.slot}',
      );
      return ChallengeRead(SyncOutcome.ok, challenge: challenge);
    } on Exception catch (e) {
      return ChallengeRead(SyncOutcome.error, detail: 'Error: $e');
    }
  }

  /// Whether the PC has drained the evidence node since the upload.
  ///
  /// The PC writes `{}` on accept and leaves a rejected payload in place, so
  /// "absent or empty object" is the accepted signal. Null when the read
  /// itself failed, so a poller can tell "still pending" from "can't see".
  Future<bool?> evidenceDrained() async {
    final client = await _open();
    if (client == null) return null;
    try {
      final text = await client.getFileText(kEvidencePath);
      if (text == null) return true;
      final decoded = jsonDecode(text);
      return decoded is Map && decoded.isEmpty;
    } on Exception {
      return null;
    }
  }

  Future<RemoteStore?> _open() async {
    try {
      return await _openClient();
    } on Object catch (error, stackTrace) {
      developer.log(
        'home-guard: could not open Firebase',
        name: 'ChallengeSync',
        error: error,
        stackTrace: stackTrace,
      );
      return null;
    }
  }
}
