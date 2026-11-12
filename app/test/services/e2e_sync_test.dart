import 'dart:convert';
import 'dart:typed_data';

import 'package:crdt_sync/crdt_sync.dart';
import 'package:crdt_sync_flutter/crdt_sync_flutter.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/e2e_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';
import 'package:home_guard_app/services/zone_sync.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../fake_remote_store.dart';
import '../fake_secure_storage.dart';

const _cheap = Argon2Params(memoryKiB: 8, iterations: 1, parallelism: 1);

const Map<String, Object?> _challengeJson = {
  'day': '2026-11-12',
  'slot': '0800',
  'zone': 'mirror',
  'token': 'secret-token-123',
  'issued_at': '2026-11-12T08:00:00+01:00',
  'consumed': false,
};

final Challenge _challenge = Challenge.fromJson(_challengeJson)!;

final _photo = EncodedPhoto(
  bytes: Uint8List.fromList([1, 2, 3]),
  base64: base64Encode([1, 2, 3]),
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late MemRemote remote;

  Future<RemoteStore?> open() =>
      openEncryptedFirebase(openClient: () async => remote, params: _cheap);

  setUp(() {
    remote = MemRemote();
    resetE2eCopyMemo();
    SharedPreferences.setMockInitialValues({});
    installFakeSecureStorage(initial: {kE2ePassphraseKey: 'test-passphrase'});
  });

  test('paths sit under the e2e layout of the old prefix', () {
    expect(E2eLayout.of(kOldSyncPrefix).prefix, kSyncPrefix);
    expect(kSyncPrefix, 'home-guard-sync-e2e');
    for (final p in [kChallengePath, kEvidencePath, kZonesPath]) {
      expect(p, startsWith('$kSyncPrefix/'));
    }
  });

  test('uploaded evidence is sealed on the wire and opens again', () async {
    final sync = ChallengeSync(openClient: open);
    final read = await sync.uploadEvidence(
      challenge: _challenge,
      photos: [_photo],
      deviceId: 'phone-1',
    );
    expect(read.outcome, SyncOutcome.ok);
    final raw = remote.files[kEvidencePath]!;
    expect(raw, isNot(contains('secret-token-123')));
    expect(raw, isNot(contains('"token"')));
    expect(raw, isNot(contains('"photos"')));
    expect(
      remote.files.keys.where((k) => k.startsWith('$kOldSyncPrefix/')),
      isEmpty,
    );
    expect(await sync.evidenceDrained(), isFalse);
    expect(e2eLocked.value, isFalse);
  });

  test('a challenge sealed by a peer is read back', () async {
    final peer = (await open())!;
    await peer.putFileText(
      kChallengePath,
      jsonEncode(_challengeJson),
      message: 'pc',
    );
    expect(remote.files[kChallengePath], isNot(contains('mirror')));
    final read = await ChallengeSync(openClient: open).fetchChallenge();
    expect(read.outcome, SyncOutcome.ok);
    expect(read.challenge!.token, 'secret-token-123');
  });

  test('zone edits are published sealed', () async {
    final zones = ZoneSync(openClient: open);
    expect(await zones.setZones(['mirror', 'toilet']), isTrue);
    expect(remote.files[kZonesPath], isNot(contains('toilet')));
    final read = await ZoneSync(openClient: open).load();
    expect(read.source, ZoneSource.synced);
  });

  test('no passphrase: locked, nothing written, no client', () async {
    installFakeSecureStorage();
    final read = await ChallengeSync(openClient: open).uploadEvidence(
      challenge: _challenge,
      photos: [_photo],
      deviceId: 'phone-1',
    );
    expect(read.outcome, SyncOutcome.notConfigured);
    expect(remote.puts, isEmpty);
    expect(e2eLocked.value, isTrue);
  });

  test('not signed in is not "locked"', () async {
    e2eLocked.value = true;
    expect(await openEncryptedFirebase(openClient: () async => null), isNull);
    expect(e2eLocked.value, isFalse);
  });

  test('a drained legacy node never clobbers a pending upload', () async {
    // The steady state of the old prefix: drained evidence, which parses as
    // an empty CRDT log. The library's one-time copy would merge it onto the
    // new path, wiping the photos and faking the PC's "accepted" signal.
    remote.files['$kOldSyncPrefix/evidence/current.json'] = '{}';
    await ChallengeSync(openClient: open).uploadEvidence(
      challenge: _challenge,
      photos: [_photo],
      deviceId: 'phone-1',
    );
    resetE2eCopyMemo(); // the app restarted
    expect(await ChallengeSync(openClient: open).evidenceDrained(), isFalse);
    expect(remote.files['$kOldSyncPrefix/evidence/current.json'], '{}');
  });
}
