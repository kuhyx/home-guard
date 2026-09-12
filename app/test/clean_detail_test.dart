import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/screens/clean_detail_screen.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/ui/theme.dart';

import 'fake_session_files.dart';

/// A 1x1 PNG: Image.memory needs bytes it can actually decode.
final _png = Uint8List.fromList([
  137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, //
  0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0, 31, 21, 196, 137, //
  0, 0, 0, 13, 73, 68, 65, 84, 120, 156, 99, 250, 207, 192, 0, 0, //
  3, 1, 1, 0, 24, 221, 141, 219, 0, 0, 0, 0, 73, 69, 78, 68, //
  174, 66, 96, 130,
]);

CleanSession _session({
  List<SessionPhoto> photos = const [],
  SessionStatus status = SessionStatus.accepted,
}) => CleanSession(
  id: 's1',
  zone: 'mirror',
  capturedAt: '2026-09-12T19:00:00Z',
  day: '2026-09-12',
  photos: photos,
  status: status,
);

Future<SessionStore> _pump(
  WidgetTester tester, {
  required CleanSession session,
  required FakeSessionFiles files,
  Uint8List? Function()? capture,
}) async {
  final store = SessionStore(files);
  await tester.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(),
      home: CleanDetailScreen(
        store: store,
        session: session,
        capture: () async => (capture ?? () => _png)(),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return store;
}

void main() {
  testWidgets('shows the clean and its photo count', (tester) async {
    final files = FakeSessionFiles()..photos['a.jpg'] = _png;
    await _pump(
      tester,
      session: _session(photos: [const SessionPhoto(name: 'a.jpg', bytes: 3)]),
      files: files,
    );
    expect(find.text('mirror'), findsOneWidget);
    expect(find.textContaining('1 photo'), findsOneWidget);
  });

  testWidgets('renders a tile per photo', (tester) async {
    final files = FakeSessionFiles()
      ..photos['a.jpg'] = _png
      ..photos['b.jpg'] = _png;
    await _pump(
      tester,
      session: _session(
        photos: const [
          SessionPhoto(name: 'a.jpg', bytes: 3),
          SessionPhoto(name: 'b.jpg', bytes: 3),
        ],
      ),
      files: files,
    );
    expect(find.byKey(const Key('photo-a.jpg')), findsOneWidget);
    expect(find.byKey(const Key('photo-b.jpg')), findsOneWidget);
  });

  testWidgets('tapping a photo opens it full screen', (tester) async {
    final files = FakeSessionFiles()..photos['a.jpg'] = _png;
    await _pump(
      tester,
      session: _session(photos: [const SessionPhoto(name: 'a.jpg', bytes: 3)]),
      files: files,
    );
    await tester.tap(find.byKey(const Key('photo-a.jpg')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('full-photo')), findsOneWidget);
  });

  testWidgets('adding a photo appends it and persists the bytes', (
    tester,
  ) async {
    final files = FakeSessionFiles()..photos['a.jpg'] = _png;
    final store = await _pump(
      tester,
      session: _session(photos: [const SessionPhoto(name: 'a.jpg', bytes: 3)]),
      files: files,
    );
    await tester.tap(find.byKey(const Key('add-photo')));
    await tester.pumpAndSettle();

    expect(find.textContaining('2 photos'), findsOneWidget);
    final stored = (await store.load()).single;
    expect(stored.photoCount, 2);
    expect(files.photos.length, 2);
  });

  testWidgets('an appended photo never reuses a freed index', (tester) async {
    // Appending to a clean whose earlier photos were pruned must not
    // overwrite a surviving file.
    final files = FakeSessionFiles()..photos['s1-05.jpg'] = _png;
    final store = await _pump(
      tester,
      session: _session(
        photos: [const SessionPhoto(name: 's1-05.jpg', bytes: 3)],
      ),
      files: files,
    );
    await tester.tap(find.byKey(const Key('add-photo')));
    await tester.pumpAndSettle();
    expect((await store.load()).single.photoNames, ['s1-05.jpg', 's1-06.jpg']);
  });

  testWidgets('cancelling the camera changes nothing', (tester) async {
    final files = FakeSessionFiles();
    final store = await _pump(
      tester,
      session: _session(),
      files: files,
      capture: () => null,
    );
    await tester.tap(find.byKey(const Key('add-photo')));
    await tester.pumpAndSettle();
    expect(await store.load(), isEmpty);
  });

  testWidgets('a clean whose photos were freed says so', (tester) async {
    await _pump(tester, session: _session(), files: FakeSessionFiles());
    expect(find.byKey(const Key('detail-empty')), findsOneWidget);
    expect(find.textContaining('record of it stays'), findsOneWidget);
  });

  testWidgets('it says where an added photo will go, before you tap', (
    tester,
  ) async {
    // A signed PC entry is closed, so a photo added afterwards is phone-only.
    // Letting the counts diverge silently would leave a clean reading 6 here
    // and 5 on the PC with no way to know why.
    await _pump(tester, session: _session(), files: FakeSessionFiles());
    expect(
      find.textContaining("PC's record of this clean is closed"),
      findsOneWidget,
    );
  });

  testWidgets('a clean still on its way to the PC says photos go with it', (
    tester,
  ) async {
    await _pump(
      tester,
      session: _session(status: SessionStatus.queued),
      files: FakeSessionFiles(),
    );
    expect(find.textContaining('new photos go with it'), findsOneWidget);
  });

  testWidgets('a self-logged clean says it never goes to the PC', (
    tester,
  ) async {
    await _pump(
      tester,
      session: _session(status: SessionStatus.selfLogged),
      files: FakeSessionFiles(),
    );
    expect(find.textContaining('never goes to the PC'), findsOneWidget);
  });

  testWidgets('there is no gallery affordance on the detail screen', (
    tester,
  ) async {
    // Viewing is not picking. Adding here still opens the camera, so the
    // anti-replay defence survives a screen full of existing photos.
    final files = FakeSessionFiles()..photos['a.jpg'] = _png;
    await _pump(
      tester,
      session: _session(photos: [const SessionPhoto(name: 'a.jpg', bytes: 3)]),
      files: files,
    );
    expect(find.byIcon(Icons.photo_library), findsNothing);
    expect(find.textContaining('gallery'), findsNothing);
    expect(find.byIcon(Icons.photo_camera), findsOneWidget);
  });
}
