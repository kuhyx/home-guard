// Guard for kuhy's textgate rule: no painted word on any screen.
//
// Every screen is pumped in each state it can show, every painted string
// (Text, RichText, EditableText, InputDecoration hints) is collected, the
// fixture's own content (zone names, ISO days, numbers) is removed, and what
// is left must hold no run of two or more letters. Spoken-only semantic
// labels are not painted and so are deliberately not collected.
import 'dart:convert';
import 'dart:typed_data';

import 'package:crdt_sync/crdt_sync.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/models/zone_history.dart';
import 'package:home_guard_app/screens/clean_detail_screen.dart';
import 'package:home_guard_app/screens/history_screen.dart';
import 'package:home_guard_app/screens/home_body.dart';
import 'package:home_guard_app/screens/home_cue.dart';
import 'package:home_guard_app/screens/home_screen.dart';
import 'package:home_guard_app/screens/log_clean_screen.dart';
import 'package:home_guard_app/screens/settings_screen.dart';
import 'package:home_guard_app/screens/zones_screen.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/services/zone_sync.dart';
import 'package:home_guard_app/ui/theme.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_remote_store.dart';
import 'fake_secure_storage.dart';
import 'fake_session_files.dart';

final _now = DateTime.utc(2026, 9, 12, 19);

/// Content on screen: zone names (the user's own, or the default rotation's
/// place names, which are data the user edits, not chrome).
const List<String> _content = [
  ...ZoneHistory.defaultZones,
  'mirror',
  'toilet',
  'shelf',
];

final _word = RegExp('[A-Za-z]{2,}');

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

/// Every string the current frame paints.
List<String> _painted(WidgetTester tester) => [
  for (final w in tester.widgetList<RichText>(find.byType(RichText)))
    w.text.toPlainText(),
  for (final w in tester.widgetList<EditableText>(find.byType(EditableText)))
    w.controller.text,
  for (final w in tester.widgetList<InputDecorator>(
    find.byType(InputDecorator),
  )) ...[
    ?w.decoration.labelText,
    ?w.decoration.hintText,
    ?w.decoration.helperText,
  ],
];

void _expectNoWords(WidgetTester tester, String where) {
  final painted = _painted(tester);
  // An empty walk means the screen did not build: that is red, not green.
  expect(painted, isNotEmpty, reason: '$where painted nothing at all');
  final words = <String>[];
  for (final raw in painted) {
    var rest = raw;
    for (final c in _content) {
      rest = rest.replaceAll(c, '');
    }
    if (_word.hasMatch(rest)) words.add(raw);
  }
  expect(words, isEmpty, reason: '$where paints words');
}

Future<void> _show(
  WidgetTester tester,
  Widget home, {
  bool settle = true,
}) async {
  await tester.pumpWidget(MaterialApp(theme: buildAppTheme(), home: home));
  // Busy phases run an endless progress animation: one frame is enough.
  settle ? await tester.pumpAndSettle() : await tester.pump();
}

HomeBody _body(HomePhase phase, {int photos = 0, HomeCue? cue}) => HomeBody(
  phase: phase,
  zones: const ['desk', 'mirror'],
  selectedZone: 'desk',
  photoCount: photos,
  cue: cue ?? HomeCue.none,
  assignedZone: 'desk',
  onZoneSelected: (_) {},
  onTakePhoto: () {},
  onFinish: () {},
  onOpenSettings: () {},
  onOpenHistory: () {},
);

CleanSession _session(SessionStatus status, {bool photos = true}) =>
    CleanSession(
      id: 's-${status.name}',
      zone: 'mirror',
      capturedAt: '2026-09-12T19:00:00Z',
      day: '2026-09-12',
      photos: photos ? const [SessionPhoto(name: 'a.jpg', bytes: 3)] : const [],
      status: status,
    );

ZoneSync _zones(RemoteStore? remote) =>
    ZoneSync(openClient: () async => remote, clock: () => _now);

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('home body paints no words in any phase or cue', (tester) async {
    for (final phase in HomePhase.values) {
      for (final cue in HomeCue.values) {
        for (final photos in [0, 3]) {
          await _show(
            tester,
            Scaffold(
              body: _body(phase, photos: photos, cue: cue),
            ),
            settle: false,
          );
          // Loading paints only a spinner; it may legitimately paint nothing.
          if (_painted(tester).isEmpty) continue;
          _expectNoWords(tester, 'home ${phase.name}/${cue.name}/$photos');
        }
      }
    }
  });

  testWidgets('home screen offline paints no words', (tester) async {
    final remote = _BrokenRemote();
    await _show(
      tester,
      HomeScreen(
        deviceId: 'dev-1',
        store: SessionStore(FakeSessionFiles()),
        sync: ChallengeSync(openClient: () async => remote, clock: () => _now),
        zoneSync: _zones(remote),
        capture: () async => Uint8List.fromList(List.filled(64, 7)),
        encode: (raw) => EncodedPhoto(bytes: raw, base64: base64Encode(raw)),
        clock: () => _now,
        confirmDelay: Duration.zero,
      ),
    );
    _expectNoWords(tester, 'home offline');
    await tester.tap(find.byKey(const Key('take-photo')));
    await tester.pumpAndSettle();
    _expectNoWords(tester, 'home one photo');
  });

  testWidgets('history, log and detail paint no words', (tester) async {
    final store = SessionStore(FakeSessionFiles());
    await _show(tester, HistoryScreen(store: store));
    // The empty state is an icon: only the FAB etc. remain, so no Text at all
    // is fine here.
    expect(_painted(tester).where(_word.hasMatch), isEmpty);

    for (final s in SessionStatus.values) {
      await store.put(_session(s));
    }
    await _show(tester, HistoryScreen(store: store));
    _expectNoWords(tester, 'history');

    await _show(
      tester,
      LogCleanScreen(
        store: store,
        zoneSync: _zones(MemRemote()),
        capture: () async => Uint8List.fromList([1, 2, 3]),
        clock: () => _now,
      ),
    );
    _expectNoWords(tester, 'log empty');
    await tester.tap(find.byKey(const Key('log-add-photo')));
    await tester.pumpAndSettle();
    _expectNoWords(tester, 'log one photo');

    for (final s in SessionStatus.values) {
      for (final photos in [true, false]) {
        await _show(
          tester,
          CleanDetailScreen(
            store: store,
            session: _session(s, photos: photos),
          ),
        );
        _expectNoWords(tester, 'detail ${s.name}/$photos');
      }
    }
  });

  testWidgets('settings and zones paint no words', (tester) async {
    installFakeSecureStorage();
    await _show(tester, const SettingsScreen());
    expect(_painted(tester).where(_word.hasMatch), isEmpty);

    await _show(tester, ZonesScreen(sync: _zones(_BrokenRemote())));
    _expectNoWords(tester, 'zones fallback');
    await tester.enterText(find.byKey(const Key('zone-input')), 'shelf');
    await tester.tap(find.byKey(const Key('zone-add')));
    await tester.pumpAndSettle();
    _expectNoWords(tester, 'zones saved locally');
    await tester.longPress(find.byKey(const Key('zone-tile-desk')));
    await tester.pumpAndSettle();
    _expectNoWords(tester, 'zone sheet');
  });
}
