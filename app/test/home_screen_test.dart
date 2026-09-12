import 'dart:convert';
import 'dart:typed_data';

import 'package:crdt_sync/crdt_sync.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
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

  testWidgets('the camera is offered with the PC completely unreachable', (
    tester,
  ) async {
    // The whole point: cleaning is done with your hands, and the PC being
    // off is not a reason the app should refuse to record it.
    await _pump(tester, remote: _BrokenRemote());
    expect(find.byKey(const Key('take-photo')), findsOneWidget);
    expect(find.textContaining('Offline'), findsOneWidget);
  });

  testWidgets('offline falls back to the default rotation', (tester) async {
    await _pump(tester, remote: _BrokenRemote());
    expect(find.byKey(const Key('zone-desk')), findsOneWidget);
    expect(find.byKey(const Key('zone-kitchen counter')), findsOneWidget);
  });

  testWidgets("pre-selects the PC's zone when it has published one", (
    tester,
  ) async {
    await _pump(tester, remote: _remoteWithZonesAndChallenge());
    expect(find.byKey(const Key('assigned')), findsOneWidget);
    expect(find.textContaining('waiting on desk'), findsOneWidget);
  });

  testWidgets('you can clean a zone the PC did not ask for', (tester) async {
    final (store, _) = await _pump(
      tester,
      remote: _remoteWithZonesAndChallenge(),
    );
    await tester.tap(find.byKey(const Key('zone-mirror')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();

    final sessions = await store.load();
    expect(sessions.single.zone, 'mirror');
  });

  testWidgets('photos accumulate with no limit and are durable', (
    tester,
  ) async {
    final (store, files) = await _pump(tester, remote: _BrokenRemote());
    for (var i = 0; i < 7; i++) {
      await tester.tap(find.byKey(const Key('take-photo')));
      await tester.pumpAndSettle();
    }
    expect(find.textContaining('7 photos so far'), findsOneWidget);

    final sessions = await store.load();
    expect(sessions.single.photoCount, 7);
    // Bytes on disk, not just a count in memory.
    expect(files.photos.length, 7);
  });

  testWidgets('the button invites another photo after the first', (
    tester,
  ) async {
    await _pump(tester, remote: _BrokenRemote());
    expect(find.text('Take a photo'), findsOneWidget);
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    expect(find.text('Another photo'), findsOneWidget);
  });

  testWidgets('the zone cannot be switched once photos exist', (tester) async {
    // Switching mid-clean would orphan the shots already taken.
    await _pump(tester, remote: _BrokenRemote());
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    final chip = tester.widget<ChoiceChip>(find.byKey(const Key('zone-desk')));
    expect(chip.onSelected, isNull);
  });

  testWidgets('cancelling the camera changes nothing', (tester) async {
    final (store, _) = await _pump(
      tester,
      remote: _BrokenRemote(),
      capture: () => null,
    );
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    expect(find.textContaining('No photo taken'), findsOneWidget);
    expect(await store.load(), isEmpty);
  });

  testWidgets('there is no gallery affordance, before or after capture', (
    tester,
  ) async {
    // Camera-only capture is load-bearing security, not a UI preference:
    // the token defeats replaying an old upload, this defeats attaching an
    // old photo. See docs/DOCS-marker-protocol.md.
    await _pump(tester, remote: _BrokenRemote());
    expect(find.byIcon(Icons.photo_library), findsNothing);
    expect(find.textContaining('gallery'), findsNothing);

    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.photo_library), findsNothing);
    expect(find.textContaining('gallery'), findsNothing);
  });
}
