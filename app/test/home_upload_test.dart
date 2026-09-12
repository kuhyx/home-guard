import 'dart:convert';
import 'dart:typed_data';

import 'package:crdt_sync/crdt_sync.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/screens/home_screen.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/services/zone_sync.dart';
import 'package:home_guard_app/ui/theme.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_remote_store.dart';
import 'fake_session_files.dart';

final _now = DateTime.utc(2026, 9, 12, 19);
const _today = '2026-09-12';

/// A PC that takes the upload and drains, which is the only real "accepted".
class _DrainingRemote extends MemRemote {
  /// What was written before the drain, so tests can still assert on it.
  String? evidenceSeen;

  @override
  Future<void> putFileText(
    String path,
    String text, {
    required String message,
  }) async {
    await super.putFileText(path, text, message: message);
    if (path == kEvidencePath) {
      evidenceSeen = text;
      files[path] = '{}';
    }
  }
}

class _BrokenRemote extends MemRemote {
  @override
  Future<String?> getFileText(String path) async =>
      throw RemoteSyncError('offline');

  @override
  Future<void> putFileText(
    String path,
    String text, {
    required String message,
  }) async => throw RemoteSyncError('offline');
}

Uint8List _raw() => Uint8List.fromList(List.filled(64, 7));

MemRemote _remoteWithZonesAndChallenge({
  bool challenge = true,
  bool draining = false,
}) {
  final remote = (draining ? _DrainingRemote() : MemRemote())
    ..files[kZonesPath] = jsonEncode({
      'v': 1,
      'e': {
        _today: {
          'zones': ['desk', 'mirror', 'toilet'],
          't': 'T1',
        },
      },
    });
  if (challenge) {
    remote.files[kChallengePath] = jsonEncode({
      'day': _today,
      'slot': '0800',
      'zone': 'desk',
      'token': 'tok',
      'issued_at': 'T',
      'consumed': false,
    });
  }
  return remote;
}

Future<(SessionStore, FakeSessionFiles)> _pump(
  WidgetTester tester, {
  required RemoteStore? remote,
  Uint8List? Function()? capture,
}) async {
  final files = FakeSessionFiles();
  final store = SessionStore(files);
  await tester.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: HomeScreen(
        deviceId: 'dev-1',
        store: store,
        sync: ChallengeSync(openClient: () async => remote, clock: () => _now),
        zoneSync: ZoneSync(openClient: () async => remote, clock: () => _now),
        capture: () async => (capture ?? _raw)(),
        encode: (raw) => EncodedPhoto(bytes: raw, base64: base64Encode(raw)),
        clock: () => _now,
        confirmDelay: Duration.zero,
      ),
    ),
  );
  await tester.pumpAndSettle();
  return (store, files);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('finishing offline saves and says so honestly', (tester) async {
    final (store, _) = await _pump(tester, remote: _BrokenRemote());
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('finish')));
    await tester.pumpAndSettle();

    expect(find.text('Saved on this phone'), findsOneWidget);
    expect(find.textContaining('will reach the PC'), findsOneWidget);
    expect((await store.load()).single.status, SessionStatus.queued);
  });

  testWidgets('finishing online uploads and reports acceptance', (
    tester,
  ) async {
    final remote = _remoteWithZonesAndChallenge(draining: true);
    final (store, _) = await _pump(tester, remote: remote);
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('finish')));
    await tester.pumpAndSettle();

    expect(find.text('Done — the PC took it'), findsOneWidget);
    expect(remote.puts, contains(kEvidencePath));
    expect((await store.load()).single.status, SessionStatus.accepted);
  });

  testWidgets('an upload the PC ignores is not reported as done', (
    tester,
  ) async {
    // The write landing is not the PC taking it. Saying "done" here would
    // be reporting the appearance of an outcome.
    final remote = _remoteWithZonesAndChallenge();
    final (store, _) = await _pump(tester, remote: remote);
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('finish')));
    await tester.pumpAndSettle();

    expect(find.text('Saved on this phone'), findsOneWidget);
    expect((await store.load()).single.status, SessionStatus.queued);
  });

  testWidgets('the upload carries every photo and the captured day', (
    tester,
  ) async {
    final remote =
        _remoteWithZonesAndChallenge(draining: true) as _DrainingRemote;
    await _pump(tester, remote: remote);
    for (var i = 0; i < 3; i++) {
      await tester.tap(find.byKey(const Key('take-photo')));
      await tester.pumpAndSettle();
    }
    await tester.tap(find.byKey(const Key('finish')));
    await tester.pumpAndSettle();

    final payload = jsonDecode(remote.evidenceSeen!) as Map<String, Object?>;
    expect((payload['photos']! as List).length, 3);
    expect(payload['captured_day'], _today);
    expect(payload['zone'], 'desk');
  });
}
