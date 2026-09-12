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
      ),
    ),
  );
  await tester.pumpAndSettle();
  return (store, files);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('past cleans are reachable and list the session', (tester) async {
    await _pump(tester, remote: _BrokenRemote());
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('finish')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('open-history')));
    await tester.pumpAndSettle();

    expect(find.text('Past cleans'), findsOneWidget);
    expect(find.text('desk'), findsOneWidget);
    expect(find.textContaining('1 photo'), findsOneWidget);
  });

  testWidgets('history is empty before anything is recorded', (tester) async {
    await _pump(tester, remote: _BrokenRemote());
    await tester.tap(find.byKey(const Key('open-history')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('history-empty')), findsOneWidget);
  });
}
