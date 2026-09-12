import 'package:crdt_sync/crdt_sync.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/screens/zones_screen.dart';
import 'package:home_guard_app/services/zone_sync.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_remote_store.dart';

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

ZoneSync _sync(RemoteStore? remote) => ZoneSync(
  openClient: () async => remote,
  clock: () => DateTime.utc(2026, 9, 12, 19),
);

/// Scoped to the rotation list, so the TextField's 'mirror' hint (good UX,
/// and a real zone name) cannot be mistaken for a list entry.
Finder _inList(String name) => find.descendant(
  of: find.byType(ReorderableListView),
  matching: find.text(name),
);

Future<void> _pump(WidgetTester tester, ZoneSync sync) async {
  await tester.pumpWidget(MaterialApp(home: ZonesScreen(sync: sync)));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('shows the default rotation with no PC and no cache', (
    tester,
  ) async {
    await _pump(tester, _sync(_BrokenRemote()));
    expect(_inList('desk'), findsOneWidget);
    expect(_inList('kitchen counter'), findsOneWidget);
    expect(find.textContaining('defaults'), findsOneWidget);
  });

  testWidgets('adding a zone works with no signal and says so', (tester) async {
    await _pump(tester, _sync(_BrokenRemote()));
    await tester.enterText(find.byKey(const Key('zone-input')), 'mirror');
    await tester.tap(find.byKey(const Key('zone-add')));
    await tester.pumpAndSettle();

    expect(_inList('mirror'), findsOneWidget);
    // The banner must be honest: saved here, not yet at the PC.
    expect(find.textContaining('when you have signal'), findsOneWidget);
  });

  testWidgets('an offline add survives a reopen', (tester) async {
    await _pump(tester, _sync(_BrokenRemote()));
    await tester.enterText(find.byKey(const Key('zone-input')), 'washbasin');
    await tester.tap(find.byKey(const Key('zone-add')));
    await tester.pumpAndSettle();

    await _pump(tester, _sync(_BrokenRemote()));
    expect(_inList('washbasin'), findsOneWidget);
  });

  testWidgets('adding publishes to the PC when reachable', (tester) async {
    final remote = MemRemote();
    await _pump(tester, _sync(remote));
    await tester.enterText(find.byKey(const Key('zone-input')), 'toilet');
    await tester.tap(find.byKey(const Key('zone-add')));
    await tester.pumpAndSettle();

    expect(remote.puts, contains(kZonesPath));
    expect(find.textContaining('sent to the PC'), findsOneWidget);
  });

  testWidgets('a duplicate add is ignored', (tester) async {
    await _pump(tester, _sync(_BrokenRemote()));
    await tester.enterText(find.byKey(const Key('zone-input')), 'desk');
    await tester.tap(find.byKey(const Key('zone-add')));
    await tester.pumpAndSettle();
    expect(_inList('desk'), findsOneWidget);
  });

  testWidgets('a blank add is ignored', (tester) async {
    await _pump(tester, _sync(_BrokenRemote()));
    await tester.enterText(find.byKey(const Key('zone-input')), '   ');
    await tester.tap(find.byKey(const Key('zone-add')));
    await tester.pumpAndSettle();
    expect(find.byType(ListTile), findsNWidgets(3));
  });

  testWidgets('removing a zone drops it', (tester) async {
    await _pump(tester, _sync(_BrokenRemote()));
    await tester.tap(find.byKey(const Key('remove-desk')));
    await tester.pumpAndSettle();
    expect(_inList('desk'), findsNothing);
    expect(find.byType(ListTile), findsNWidgets(2));
  });

  testWidgets('the last zone cannot be removed', (tester) async {
    await _pump(tester, _sync(_BrokenRemote()));
    await tester.tap(find.byKey(const Key('remove-desk')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('remove-kitchen counter')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('remove-entryway')));
    await tester.pumpAndSettle();

    expect(_inList('entryway'), findsOneWidget);
    expect(find.textContaining('at least one zone'), findsOneWidget);
  });

  testWidgets('there is no gallery affordance anywhere on this screen', (
    tester,
  ) async {
    // Camera-only capture is load-bearing security; no screen may introduce
    // a picker, however unrelated it looks.
    await _pump(tester, _sync(_BrokenRemote()));
    expect(find.byIcon(Icons.photo_library), findsNothing);
    expect(find.textContaining('gallery'), findsNothing);
  });
}
