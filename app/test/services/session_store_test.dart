import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/services/session_store.dart';

import '../fake_session_files.dart';

CleanSession _session(
  String id, {
  String day = '2026-09-12',
  SessionStatus status = SessionStatus.draft,
  List<String> photos = const [],
  String at = '2026-09-12T19:00:00Z',
}) => CleanSession(
  id: id,
  zone: 'mirror',
  capturedAt: at,
  day: day,
  photos: [for (final n in photos) SessionPhoto(name: n, bytes: 1)],
  status: status,
);

Uint8List _bytes(int n) => Uint8List.fromList(List.filled(8, n));

void main() {
  late FakeSessionFiles files;
  late SessionStore store;

  setUp(() {
    files = FakeSessionFiles();
    store = SessionStore(files);
  });

  test('an empty store loads nothing', () async {
    expect(await store.load(), isEmpty);
  });

  test('a session round-trips', () async {
    await store.put(_session('s1'));
    final loaded = await store.load();
    expect(loaded.single.id, 's1');
    expect(loaded.single.zone, 'mirror');
  });

  test('put replaces rather than duplicating', () async {
    await store.put(_session('s1'));
    await store.put(_session('s1', status: SessionStatus.queued));
    final loaded = await store.load();
    expect(loaded.length, 1);
    expect(loaded.single.status, SessionStatus.queued);
  });

  test('sessions load newest first', () async {
    await store.put(_session('old', at: '2026-09-01T10:00:00Z'));
    await store.put(_session('new', at: '2026-09-12T10:00:00Z'));
    expect((await store.load()).map((s) => s.id), ['new', 'old']);
  });

  test('a corrupt index is survivable, not fatal', () async {
    files.index = '{not json';
    expect(await store.load(), isEmpty);
  });

  test('a non-list index is survivable', () async {
    files.index = '{"a": 1}';
    expect(await store.load(), isEmpty);
  });

  test('unparsable rows are skipped, good ones kept', () async {
    files.index = jsonEncode([
      {'nope': true},
      _session('good').toJson(),
    ]);
    expect((await store.load()).single.id, 'good');
  });

  group('addPhoto', () {
    test('stores bytes and appends an indexed name', () async {
      var s = _session('s1');
      s = await store.addPhoto(s, _bytes(1));
      s = await store.addPhoto(s, _bytes(2));
      expect(s.photoNames, ['s1-00.jpg', 's1-01.jpg']);
      expect(files.photos['s1-01.jpg'], _bytes(2));
    });

    test('photo bytes are durable across a reload', () async {
      var s = _session('s1');
      s = await store.addPhoto(s, _bytes(7));
      final reloaded = await SessionStore(files).load();
      expect(reloaded.single.photoNames, ['s1-00.jpg']);
      expect(await SessionStore(files).photo('s1-00.jpg'), _bytes(7));
    });

    test('there is no cap on how many photos one clean takes', () async {
      var s = _session('s1');
      for (var i = 0; i < 50; i++) {
        s = await store.addPhoto(s, _bytes(i));
      }
      expect(s.photoCount, 50);
    });
  });

  test('queued returns only queued sessions, oldest first', () async {
    await store.put(
      _session('a', status: SessionStatus.queued, at: '2026-09-01T10:00:00Z'),
    );
    await store.put(_session('b'));
    await store.put(
      _session('c', status: SessionStatus.queued, at: '2026-09-12T10:00:00Z'),
    );
    expect((await store.queued()).map((s) => s.id), ['a', 'c']);
  });

  test('remove deletes the session and its photos', () async {
    var s = _session('s1');
    s = await store.addPhoto(s, _bytes(1));
    await store.remove('s1');
    expect(await store.load(), isEmpty);
    expect(files.deleted, ['s1-00.jpg']);
  });

  group('prune', () {
    test('frees oldest accepted photos until the budget fits', () async {
      for (final id in ['old', 'mid', 'new']) {
        var s = _session(
          id,
          at: '2026-09-0${['old', 'mid', 'new'].indexOf(id) + 1}T10:00:00Z',
        );
        s = await store.addPhoto(s, _bytes(1));
        await store.put(s.copyWith(status: SessionStatus.accepted));
      }
      // 3 photos x 8 bytes = 24; a 16-byte budget must free exactly one.
      await store.prune(budgetBytes: 16);

      final loaded = await store.load();
      final byId = {for (final s in loaded) s.id: s};
      expect(byId['old']!.photos, isEmpty, reason: 'oldest freed first');
      expect(byId['mid']!.photos, isNotEmpty);
      expect(byId['new']!.photos, isNotEmpty);
      // The record survives its images.
      expect(byId['old']!.status, SessionStatus.accepted);
      expect(files.deleted, ['old-00.jpg']);
    });

    test('does nothing while inside the budget', () async {
      var s = _session('s1');
      s = await store.addPhoto(s, _bytes(1));
      await store.put(s.copyWith(status: SessionStatus.accepted));
      await store.prune(budgetBytes: 1000);
      expect(files.deleted, isEmpty);
    });

    test('never frees a clean that has not reached the PC', () async {
      // Discarding un-credited work is the failure this store exists to
      // prevent, so a tight budget must not reach it.
      var s = _session('queued', at: '2020-01-01T10:00:00Z');
      s = await store.addPhoto(s, _bytes(1));
      await store.put(s.copyWith(status: SessionStatus.queued));

      await store.prune(budgetBytes: 0);

      expect((await store.load()).single.photos, isNotEmpty);
      expect(files.deleted, isEmpty);
    });

    test('never frees a self-logged clean', () async {
      var s = _session('self', at: '2020-01-01T10:00:00Z');
      s = await store.addPhoto(s, _bytes(1));
      await store.put(s.copyWith(status: SessionStatus.selfLogged));
      await store.prune(budgetBytes: 0);
      expect((await store.load()).single.photos, isNotEmpty);
    });

    test('totalBytes sums every stored photo', () async {
      var s = _session('s1');
      s = await store.addPhoto(s, _bytes(1));
      s = await store.addPhoto(s, _bytes(2));
      await store.put(s);
      expect(await store.totalBytes(), 16);
    });
  });

  group('CleanSession', () {
    test('fromJson rejects anything that is not a manifest', () {
      expect(CleanSession.fromJson(null), isNull);
      expect(CleanSession.fromJson('nope'), isNull);
      expect(CleanSession.fromJson(<String, Object?>{'id': 1}), isNull);
    });

    test('an unknown status falls back to queued, never silently accepted', () {
      final s = CleanSession.fromJson({
        'id': 'x',
        'zone': 'mirror',
        'captured_at': 'T',
        'day': '2026-09-12',
        'photos': <String>[],
        'status': 'from-the-future',
      });
      expect(s!.status, SessionStatus.queued);
    });

    test('optional fields round-trip', () {
      final s = _session(
        's1',
      ).copyWith(slot: '0800', token: 'tok', detail: 'why');
      final back = CleanSession.fromJson(jsonDecode(jsonEncode(s.toJson())));
      expect(back!.slot, '0800');
      expect(back.token, 'tok');
      expect(back.detail, 'why');
    });
  });
}
