import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/screens/history_screen.dart';
import 'package:home_guard_app/screens/home_body.dart';
import 'package:home_guard_app/screens/home_cue.dart';
import 'package:home_guard_app/screens/zones_screen.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/services/zone_sync.dart';
import 'package:home_guard_app/ui/theme.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_remote_store.dart';
import 'fake_session_files.dart';

/// Pixel 6a: 1080x2400 px at 2.625, real status bar and nav inset.
void _pixel6a(WidgetTester tester) {
  tester.view
    ..physicalSize = const Size(1080, 2400)
    ..devicePixelRatio = 2.625
    ..padding = const FakeViewPadding(top: 132, bottom: 63);
  addTearDown(tester.view.reset);
}

/// Every vertical Scrollable must have nothing left to scroll to.
void _expectNoVerticalScroll(WidgetTester tester) {
  final states = tester.stateList<ScrollableState>(find.byType(Scrollable));
  for (final s in states) {
    if (s.position.axis != Axis.vertical) continue;
    expect(s.position.maxScrollExtent, 0, reason: 'vertical scroll left');
  }
}

List<String> _zones(int n) => [for (var i = 0; i < n; i++) 'zone number $i'];

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('home: 40 zones, no vertical scroll, actions hittable', (
    tester,
  ) async {
    _pixel6a(tester);
    var taken = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: Scaffold(
          appBar: AppBar(),
          body: HomeBody(
            phase: HomePhase.ready,
            zones: _zones(40),
            selectedZone: 'zone number 0',
            photoCount: 2,
            cue: HomeCue.savedOffline,
            assignedZone: 'zone number 3',
            onZoneSelected: (_) {},
            onTakePhoto: () => taken++,
            onFinish: () {},
            onOpenSettings: () {},
            onOpenHistory: () {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    _expectNoVerticalScroll(tester);
    final screen = tester.view.physicalSize / tester.view.devicePixelRatio;
    final bottom = screen.height - 63 / 2.625;
    for (final k in ['take-photo', 'finish', 'open-history']) {
      final r = tester.getRect(find.byKey(Key(k)));
      expect(r.bottom, lessThanOrEqualTo(bottom), reason: k);
    }
    await tester.tap(find.byKey(const Key('take-photo')));
    expect(taken, 1);
  });

  testWidgets('zones: 40 zones, no vertical scroll, add row hittable', (
    tester,
  ) async {
    _pixel6a(tester);
    final sync = ZoneSync(
      openClient: () async => MemRemote(),
      clock: () => DateTime.utc(2026, 9, 12, 19),
    );
    await sync.setZones(_zones(40));
    await tester.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: ZonesScreen(sync: sync),
      ),
    );
    await tester.pumpAndSettle();

    _expectNoVerticalScroll(tester);
    expect(find.byKey(const Key('zone-add')).hitTestable(), findsOneWidget);
  });

  testWidgets('history: 90 cleans, no vertical scroll, FAB hittable', (
    tester,
  ) async {
    _pixel6a(tester);
    final store = SessionStore(FakeSessionFiles());
    for (var i = 0; i < 90; i++) {
      await store.put(
        CleanSession(
          id: 's$i',
          zone: 'zone number ${i % 7}',
          capturedAt: DateTime.utc(2026, 9, 12, 19).toIso8601String(),
          day: '2026-09-${(i % 28 + 1).toString().padLeft(2, '0')}',
          photos: const [],
          status: SessionStatus.accepted,
        ),
      );
    }
    await tester.pumpWidget(
      MaterialApp(
        theme: buildAppTheme(),
        home: HistoryScreen(store: store),
      ),
    );
    await tester.pumpAndSettle();

    _expectNoVerticalScroll(tester);
    expect(find.byKey(const Key('log-a-clean')).hitTestable(), findsOneWidget);
    expect(find.byKey(const Key('history-s0')).hitTestable(), findsOneWidget);
  });
}
