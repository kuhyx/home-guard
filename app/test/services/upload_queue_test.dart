import 'dart:convert';
import 'dart:typed_data';

import 'package:crdt_sync/crdt_sync.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/services/upload_queue.dart';

import '../fake_remote_store.dart';
import '../fake_session_files.dart';

final _now = DateTime.utc(2026, 9, 12, 19);
const _today = '2026-09-12';

class _BrokenRemote extends MemRemote {
  @override
  Future<String?> getFileText(String path) async =>
      throw RemoteSyncError('offline');
}

MemRemote _withChallenge({
  String day = _today,
  bool consumed = false,
  bool draining = false,
  String token = 'tok',
}) =>
    (draining ? _DrainingRemote() : MemRemote())
      ..files[kChallengePath] = jsonEncode({
        'day': day,
        'slot': '0800',
        'zone': 'desk',
        'token': token,
        'issued_at': 'T',
        'consumed': consumed,
      });

UploadQueue _queue(SessionStore store, RemoteStore? remote) => UploadQueue(
  store: store,
  sync: ChallengeSync(openClient: () async => remote, clock: () => _now),
  deviceId: 'dev-1',
  clock: () => _now,
  encode: (raw) => EncodedPhoto(bytes: raw, base64: base64Encode(raw)),
  confirmDelay: Duration.zero,
);

/// A remote that accepts the write and then drains, like a running PC.
class _DrainingRemote extends MemRemote {
  /// What was written before the drain, so tests can still assert on it.
  String? lastEvidence;

  @override
  Future<void> putFileText(
    String path,
    String text, {
    required String message,
  }) async {
    await super.putFileText(path, text, message: message);
    if (path == kEvidencePath) {
      lastEvidence = text;
      files[path] = '{}';
    }
  }
}

Future<SessionStore> _storeWith(
  FakeSessionFiles files, {
  String day = _today,
  int photos = 1,
  String zone = 'mirror',
}) async {
  final store = SessionStore(files);
  var session = CleanSession(
    id: 's1',
    zone: zone,
    capturedAt: '${day}T19:00:00Z',
    day: day,
    photoNames: const [],
    status: SessionStatus.draft,
  );
  for (var i = 0; i < photos; i++) {
    session = await store.addPhoto(session, Uint8List.fromList([i, i, i]));
  }
  await store.put(session.copyWith(status: SessionStatus.queued));
  return store;
}

void main() {
  test('an empty queue does nothing', () async {
    final report = await _queue(SessionStore(FakeSessionFiles()), null).drain();
    expect(report.uploaded, 0);
  });

  test('a same-day session binds to the current challenge', () async {
    // The session had no token -- the PC mints those and was not there when
    // the cleaning happened. Binding on drain is the only way an offline
    // clean can ever be credited.
    final remote = _withChallenge(draining: true) as _DrainingRemote;
    final store = await _storeWith(FakeSessionFiles(), photos: 3);
    final report = await _queue(store, remote).drain();

    expect(report.uploaded, 1);
    final payload = jsonDecode(remote.lastEvidence!) as Map<String, Object?>;
    expect(payload['token'], 'tok');
    expect(payload['zone'], 'mirror');
    expect((payload['photos']! as List).length, 3);
    expect((await store.load()).single.status, SessionStatus.accepted);
  });

  test('an older session is kept as a record, not dropped', () async {
    // Binding yesterday's cleaning to today's challenge would consume
    // today's single-use token for work that lands in yesterday's log
    // bucket, leaving today both uncredited and unclearable.
    final remote = _withChallenge();
    final store = await _storeWith(FakeSessionFiles(), day: '2026-09-10');
    final report = await _queue(store, remote).drain();

    expect(report.kept, 1);
    expect(report.uploaded, 0);
    expect(remote.puts, isEmpty);
    final session = (await store.load()).single;
    expect(session.status, SessionStatus.rejected);
    expect(session.detail, contains('Kept as a record'));
    // The photos are still there; the work is not erased.
    expect(session.photoCount, 1);
  });

  test('with no signal the session stays queued for next time', () async {
    final store = await _storeWith(FakeSessionFiles());
    final report = await _queue(store, _BrokenRemote()).drain();
    expect(report.stillQueued, 1);
    expect((await store.load()).single.status, SessionStatus.queued);
  });

  test('with no challenge published the session stays queued', () async {
    final store = await _storeWith(FakeSessionFiles());
    final report = await _queue(store, MemRemote()).drain();
    expect(report.stillQueued, 1);
    expect((await store.load()).single.status, SessionStatus.queued);
  });

  test('an already-consumed challenge leaves the session queued', () async {
    final store = await _storeWith(FakeSessionFiles());
    final report = await _queue(store, _withChallenge(consumed: true)).drain();
    expect(report.stillQueued, 1);
  });

  test('a challenge for another day leaves the session queued', () async {
    final store = await _storeWith(FakeSessionFiles());
    final remote = _withChallenge(day: '2026-09-01');
    expect((await _queue(store, remote).drain()).stillQueued, 1);
  });

  test('a session whose photo files vanished is not uploaded empty', () async {
    final files = FakeSessionFiles();
    final store = await _storeWith(files);
    files.photos.clear();
    final report = await _queue(store, _withChallenge()).drain();
    expect(report.uploaded, 0);
    expect(report.stillQueued, 1);
  });

  test('an upload the PC never takes is NOT shown as accepted', () async {
    // "The write succeeded" is not "the PC took it": a rejected payload sits
    // on the node untouched. A green tick it did not earn would be reporting
    // the appearance of an outcome.
    final remote = _withChallenge();
    final store = await _storeWith(FakeSessionFiles());
    final report = await _queue(store, remote).drain();

    expect(report.uploaded, 0);
    expect(report.stillQueued, 1);
    final session = (await store.load()).single;
    expect(session.status, SessionStatus.queued);
    expect(session.detail, contains('waiting for the PC'));
    // It remembers what it was sent against, so a later drain can settle it.
    expect(session.token, 'tok');
  });

  test('a consumed challenge settles a session we never saw drain', () async {
    final store = await _storeWith(FakeSessionFiles());
    // First pass uploads but never sees the drain.
    await _queue(store, _withChallenge()).drain();
    expect((await store.load()).single.status, SessionStatus.queued);

    // The PC republishes the record as consumed once it accepts.
    final report = await _queue(store, _withChallenge(consumed: true)).drain();
    expect(report.uploaded, 1);
    final settled = (await store.load()).single;
    expect(settled.status, SessionStatus.accepted);
    // A green tick still captioned "waiting to confirm" contradicts itself.
    expect(settled.detail, isEmpty);
  });

  test('a consumed challenge for a DIFFERENT token settles nothing', () async {
    final store = await _storeWith(FakeSessionFiles());
    await _queue(store, _withChallenge()).drain();
    final report = await _queue(
      store,
      _withChallenge(consumed: true, token: 'other'),
    ).drain();
    expect(report.uploaded, 0);
    expect((await store.load()).single.status, SessionStatus.queued);
  });

  test('an unencodable photo is skipped, not fatal', () async {
    final files = FakeSessionFiles();
    final store = await _storeWith(files, photos: 2);
    final remote = _withChallenge(draining: true) as _DrainingRemote;
    var calls = 0;
    final queue = UploadQueue(
      store: store,
      sync: ChallengeSync(openClient: () async => remote, clock: () => _now),
      deviceId: 'dev-1',
      clock: () => _now,
      encode: (raw) {
        calls++;
        if (calls == 1) throw const FormatException('bad');
        return EncodedPhoto(bytes: raw, base64: base64Encode(raw));
      },
      confirmDelay: Duration.zero,
    );
    expect((await queue.drain()).uploaded, 1);
    final payload = jsonDecode(remote.lastEvidence!) as Map<String, Object?>;
    expect((payload['photos']! as List).length, 1);
  });

  test('only queued sessions are touched', () async {
    final files = FakeSessionFiles();
    final store = SessionStore(files);
    await store.put(
      const CleanSession(
        id: 'draft',
        zone: 'desk',
        capturedAt: '${_today}T10:00:00Z',
        day: _today,
        photoNames: [],
        status: SessionStatus.draft,
      ),
    );
    final report = await _queue(store, _withChallenge()).drain();
    expect(report.uploaded, 0);
    expect((await store.load()).single.status, SessionStatus.draft);
  });
}
