import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';

import '../fake_remote_store.dart';

const Map<String, Object?> _challengeJson = {
  'day': '2026-09-11',
  'slot': '0800',
  'zone': 'desk',
  'token': 'tok-1',
  'issued_at': '2026-09-11T08:00:00+02:00',
  'consumed': false,
};

final _photo = EncodedPhoto(
  bytes: Uint8List.fromList([1, 2, 3]),
  base64: base64Encode([1, 2, 3]),
);

void main() {
  group('fetchChallenge', () {
    test('parses what the PC published', () async {
      final remote = MemRemote()
        ..files[kChallengePath] = jsonEncode(_challengeJson);
      final read = await ChallengeSync(
        openClient: () async => remote,
      ).fetchChallenge();
      expect(read.outcome, SyncOutcome.ok);
      expect(read.challenge!.zone, 'desk');
    });

    test('nothing published reads as noChallenge', () async {
      final read = await ChallengeSync(
        openClient: () async => MemRemote(),
      ).fetchChallenge();
      expect(read.outcome, SyncOutcome.noChallenge);
    });

    test('an unparsable payload reads as noChallenge with a reason', () async {
      final remote = MemRemote()..files[kChallengePath] = '{"day": 1}';
      final read = await ChallengeSync(
        openClient: () async => remote,
      ).fetchChallenge();
      expect(read.outcome, SyncOutcome.noChallenge);
      expect(read.detail, contains('nothing readable'));
    });

    test('no client is notConfigured, pointing at Settings', () async {
      final read = await ChallengeSync(
        openClient: () async => null,
      ).fetchChallenge();
      expect(read.outcome, SyncOutcome.notConfigured);
      expect(read.detail, contains('Settings'));
    });

    test('a failing open is notConfigured, never a throw', () async {
      final read = await ChallengeSync(
        openClient: () async => throw StateError('keystore'),
      ).fetchChallenge();
      expect(read.outcome, SyncOutcome.notConfigured);
    });

    test('a failing read is an error with the message', () async {
      final read = await ChallengeSync(
        openClient: () async => BrokenRemote(),
      ).fetchChallenge();
      expect(read.outcome, SyncOutcome.error);
      expect(read.detail, contains('offline'));
    });
  });

  group('uploadEvidence', () {
    final challenge = Challenge.fromJson(_challengeJson)!;

    test('echoes the challenge fields verbatim with the photo', () async {
      final remote = MemRemote();
      final sync = ChallengeSync(
        openClient: () async => remote,
        clock: () => DateTime.utc(2026, 9, 11, 7, 30),
      );
      final result = await sync.uploadEvidence(
        challenge: challenge,
        photos: [_photo],
        deviceId: 'phone-1',
      );
      expect(result.outcome, SyncOutcome.ok);
      expect(remote.puts, [kEvidencePath]);
      final written =
          jsonDecode(remote.files[kEvidencePath]!) as Map<String, Object?>;
      expect(written, {
        'day': '2026-09-11',
        'slot': '0800',
        'zone': 'desk',
        'token': 'tok-1',
        'device_id': 'phone-1',
        'captured_at': '2026-09-11T07:30:00.000Z',
        'captured_day': '2026-09-11',
        'photos': [
          {
            'b64': base64Encode([1, 2, 3]),
            'mime': 'image/jpeg',
          },
        ],
      });
    });

    test('carries every photo of a multi-shot clean', () async {
      final remote = MemRemote();
      final sync = ChallengeSync(openClient: () async => remote);
      await sync.uploadEvidence(
        challenge: challenge,
        photos: [_photo, _photo, _photo],
        deviceId: 'phone-1',
      );
      final written =
          jsonDecode(remote.files[kEvidencePath]!) as Map<String, Object?>;
      expect((written['photos']! as List).length, 3);
    });

    test('sends the zone actually cleaned, not the one assigned', () async {
      // The PC checks membership of the rotation, so five photos of a
      // mirror are not thrown away because the cursor pointed at the desk.
      final remote = MemRemote();
      final sync = ChallengeSync(openClient: () async => remote);
      await sync.uploadEvidence(
        challenge: challenge,
        photos: [_photo],
        deviceId: 'phone-1',
        zone: 'mirror',
      );
      final written =
          jsonDecode(remote.files[kEvidencePath]!) as Map<String, Object?>;
      expect(written['zone'], 'mirror');
      // token/day/slot still come from the challenge, untouched.
      expect(written['token'], 'tok-1');
    });

    test(
      'reports when the photos were taken, not when they were sent',
      () async {
        final remote = MemRemote();
        final sync = ChallengeSync(
          openClient: () async => remote,
          clock: () => DateTime.utc(2026, 9, 12, 10),
        );
        await sync.uploadEvidence(
          challenge: challenge,
          photos: [_photo],
          deviceId: 'phone-1',
          capturedAt: DateTime.utc(2026, 9, 11, 20),
        );
        final written =
            jsonDecode(remote.files[kEvidencePath]!) as Map<String, Object?>;
        expect(written['captured_at'], '2026-09-11T20:00:00.000Z');
      },
    );

    test('no client is notConfigured and writes nothing', () async {
      final result = await ChallengeSync(
        openClient: () async => null,
      ).uploadEvidence(challenge: challenge, photos: [_photo], deviceId: 'p');
      expect(result.outcome, SyncOutcome.notConfigured);
    });

    test('a failing write is an error', () async {
      final result = await ChallengeSync(
        openClient: () async => BrokenRemote(),
      ).uploadEvidence(challenge: challenge, photos: [_photo], deviceId: 'p');
      expect(result.outcome, SyncOutcome.error);
    });
  });

  group('evidenceDrained', () {
    test('true when the PC wrote {} or nothing is there', () async {
      final remote = MemRemote()..files[kEvidencePath] = '{}';
      final sync = ChallengeSync(openClient: () async => remote);
      expect(await sync.evidenceDrained(), isTrue);
      remote.files.remove(kEvidencePath);
      expect(await sync.evidenceDrained(), isTrue);
    });

    test('false while the payload is still sitting there', () async {
      final remote = MemRemote()..files[kEvidencePath] = '{"token": "x"}';
      expect(
        await ChallengeSync(openClient: () async => remote).evidenceDrained(),
        isFalse,
      );
    });

    test('null when it cannot be read', () async {
      expect(
        await ChallengeSync(openClient: () async => null).evidenceDrained(),
        isNull,
      );
      expect(
        await ChallengeSync(
          openClient: () async => BrokenRemote(),
        ).evidenceDrained(),
        isNull,
      );
    });
  });
}
