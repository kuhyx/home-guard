import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/screens/log_clean_screen.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/services/zone_sync.dart';
import 'package:home_guard_app/ui/theme.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_remote_store.dart';
import 'fake_session_files.dart';

final _now = DateTime.utc(2026, 9, 12, 19);
const _today = '2026-09-12';

MemRemote _zonesRemote() => MemRemote()
  ..files[kZonesPath] = jsonEncode({
    'v': 1,
    'e': {
      _today: {
        'zones': ['desk', 'mirror', 'toilet'],
        't': 'T1',
      },
    },
  });

Future<SessionStore> _pump(
  WidgetTester tester, {
  Uint8List? Function()? capture,
}) async {
  final store = SessionStore(FakeSessionFiles());
  await tester.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: LogCleanScreen(
        store: store,
        zoneSync: ZoneSync(
          openClient: () async => _zonesRemote(),
          clock: () => _now,
        ),
        capture: () async =>
            (capture ?? () => Uint8List.fromList([1, 2, 3]))(),
        clock: () => _now,
      ),
    ),
  );
  await tester.pumpAndSettle();
  return store;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('offers the rotation and defaults to today', (tester) async {
    await _pump(tester);
    expect(find.byKey(const Key('log-zone-mirror')), findsOneWidget);
    expect(find.text(_today), findsOneWidget);
  });

  testWidgets('saving is blocked until there is a photo', (tester) async {
    await _pump(tester);
    final save = tester.widget<OutlinedButton>(
      find.byKey(const Key('log-save')),
    );
    expect(save.onPressed, isNull);
    expect(find.textContaining('at least one photo'), findsOneWidget);
  });

  testWidgets('a logged clean is stored as self-logged, never queued', (
    tester,
  ) async {
    // It must not be uploaded: binding a backdated clean to today's
    // single-use token would spend it on a past log bucket.
    final store = await _pump(tester);
    await tester.tap(find.byKey(const Key('log-zone-toilet')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('log-add-photo')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('log-save')));
    await tester.pumpAndSettle();

    final stored = (await store.load()).single;
    expect(stored.zone, 'toilet');
    expect(stored.status, SessionStatus.selfLogged);
    expect(stored.photoCount, 1);
  });

  testWidgets('it says plainly that this is a record, not a claim', (
    tester,
  ) async {
    await _pump(tester);
    await tester.tap(find.byKey(const Key('log-add-photo')));
    await tester.pumpAndSettle();
    expect(find.textContaining('record, not a claim'), findsOneWidget);
  });

  testWidgets('the zone cannot change once photos exist', (tester) async {
    await _pump(tester);
    await tester.tap(find.byKey(const Key('log-add-photo')));
    await tester.pumpAndSettle();
    final chip = tester.widget<ChoiceChip>(
      find.byKey(const Key('log-zone-mirror')),
    );
    expect(chip.onSelected, isNull);
  });

  testWidgets('cancelling the camera stores nothing', (tester) async {
    final store = await _pump(tester, capture: () => null);
    await tester.tap(find.byKey(const Key('log-add-photo')));
    await tester.pumpAndSettle();
    expect(await store.load(), isEmpty);
  });

  testWidgets('there is no gallery affordance when logging', (tester) async {
    // A backdated clean is the most tempting place to allow an old photo,
    // which is exactly why it must not.
    await _pump(tester);
    expect(find.byIcon(Icons.photo_library), findsNothing);
    expect(find.textContaining('gallery'), findsNothing);
    expect(find.byIcon(Icons.photo_camera), findsOneWidget);
  });
}
