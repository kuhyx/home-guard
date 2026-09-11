import 'dart:convert';
import 'dart:typed_data';

import 'package:crdt_sync/crdt_sync.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/screens/home_screen.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';
import 'package:home_guard_app/ui/theme.dart';

import 'fake_remote_store.dart';
import 'fake_secure_storage.dart';

/// Reads fine, but every write fails -- a network that dropped mid-flow.
class _ReadOnlyRemote extends MemRemote {
  @override
  Future<void> putFileText(
    String path,
    String text, {
    required String message,
  }) async => throw RemoteSyncError('offline');
}

const Map<String, Object?> _challengeJson = {
  'day': '2026-09-11',
  'slot': '0800',
  'zone': 'desk',
  'token': 'tok-1',
  'issued_at': '2026-09-11T08:00:00+02:00',
  'consumed': false,
};

DateTime _today() => DateTime(2026, 9, 11, 9);

EncodedPhoto _fakeEncode(Uint8List raw) =>
    EncodedPhoto(bytes: raw, base64: base64Encode(raw));

Widget _app(HomeScreen screen) =>
    MaterialApp(theme: buildAppTheme(), home: screen);

HomeScreen _screen({
  required MemRemote? remote,
  Future<Uint8List?> Function()? capture,
  int pollAttempts = 3,
}) => HomeScreen(
  deviceId: 'phone-1',
  sync: ChallengeSync(openClient: () async => remote, clock: _today),
  capture: capture ?? () async => Uint8List.fromList([9, 9, 9]),
  encode: _fakeEncode,
  clock: _today,
  pollInterval: const Duration(milliseconds: 10),
  pollAttempts: pollAttempts,
);

String _text(WidgetTester t, String key) =>
    t.widget<Text>(find.byKey(Key(key))).data!;

void main() {
  testWidgets('shows the zone and the camera button when due', (t) async {
    final remote = MemRemote()
      ..files[kChallengePath] = jsonEncode(_challengeJson);
    await t.pumpWidget(_app(_screen(remote: remote)));
    await t.pump();
    expect(_text(t, 'headline'), 'desk');
    expect(find.byKey(const Key('take-photo')), findsOneWidget);
    // The anti-replay half that lives in the UI: no gallery path exists.
    expect(find.textContaining('gallery', findRichText: true), findsNothing);
    expect(find.byIcon(Icons.photo_library), findsNothing);
  });

  testWidgets('offers Settings when Firebase is not configured', (t) async {
    await t.pumpWidget(_app(_screen(remote: null)));
    await t.pump();
    expect(_text(t, 'headline'), 'Not connected');
    expect(find.byKey(const Key('open-settings')), findsOneWidget);
    expect(find.byKey(const Key('take-photo')), findsNothing);
  });

  testWidgets('nothing published: no button, says nothing is due', (t) async {
    await t.pumpWidget(_app(_screen(remote: MemRemote())));
    await t.pump();
    expect(_text(t, 'headline'), 'Nothing due');
    expect(find.byKey(const Key('take-photo')), findsNothing);
  });

  testWidgets('a consumed challenge is done, with no button', (t) async {
    final remote = MemRemote()
      ..files[kChallengePath] = jsonEncode({
        ..._challengeJson,
        'consumed': true,
      });
    await t.pumpWidget(_app(_screen(remote: remote)));
    await t.pump();
    expect(_text(t, 'headline'), 'Done for today');
    expect(find.byKey(const Key('take-photo')), findsNothing);
  });

  testWidgets("a stale challenge (another day) can't be satisfied", (t) async {
    final remote = MemRemote()
      ..files[kChallengePath] = jsonEncode({
        ..._challengeJson,
        'day': '2026-09-10',
      });
    await t.pumpWidget(_app(_screen(remote: remote)));
    await t.pump();
    expect(_text(t, 'headline'), 'Nothing due yet');
    expect(_text(t, 'detail'), contains('2026-09-10'));
    expect(find.byKey(const Key('take-photo')), findsNothing);
    expect(remote.puts, isEmpty);
  });

  testWidgets('photo -> upload -> PC drains -> accepted', (t) async {
    final remote = MemRemote()
      ..files[kChallengePath] = jsonEncode(_challengeJson);
    await t.pumpWidget(_app(_screen(remote: remote)));
    await t.pump();
    await t.tap(find.byKey(const Key('take-photo')));
    await t.pump();
    // Uploaded: the echo is on the wire with the token verbatim.
    final written =
        jsonDecode(remote.files[kEvidencePath]!) as Map<String, Object?>;
    expect(written['token'], 'tok-1');
    expect(written['device_id'], 'phone-1');
    // The PC accepts by draining the node.
    remote.files[kEvidencePath] = '{}';
    await t.pump(const Duration(milliseconds: 20));
    await t.pump();
    expect(_text(t, 'detail'), contains('accepted'));
  });

  testWidgets('never confirmed within the poll window says so', (t) async {
    final remote = MemRemote()
      ..files[kChallengePath] = jsonEncode(_challengeJson);
    await t.pumpWidget(_app(_screen(remote: remote, pollAttempts: 2)));
    await t.pump();
    await t.tap(find.byKey(const Key('take-photo')));
    await t.pump();
    await t.pump(const Duration(milliseconds: 15));
    await t.pump(const Duration(milliseconds: 15));
    await t.pump();
    expect(_text(t, 'detail'), contains('not accepted it yet'));
    // Retrying is still offered.
    expect(find.byKey(const Key('take-photo')), findsOneWidget);
  });

  testWidgets('backing out of the camera uploads nothing', (t) async {
    final remote = MemRemote()
      ..files[kChallengePath] = jsonEncode(_challengeJson);
    await t.pumpWidget(
      _app(_screen(remote: remote, capture: () async => null)),
    );
    await t.pump();
    await t.tap(find.byKey(const Key('take-photo')));
    await t.pump();
    expect(remote.puts, isEmpty);
    expect(_text(t, 'detail'), 'No photo taken.');
  });

  testWidgets('an encoder failure is reported, not thrown', (t) async {
    final remote = MemRemote()
      ..files[kChallengePath] = jsonEncode(_challengeJson);
    await t.pumpWidget(
      _app(
        HomeScreen(
          deviceId: 'p',
          sync: ChallengeSync(openClient: () async => remote, clock: _today),
          capture: () async => Uint8List.fromList([1]),
          encode: (_) => throw PhotoTooLargeError(1),
          clock: _today,
        ),
      ),
    );
    await t.pump();
    await t.tap(find.byKey(const Key('take-photo')));
    await t.pump();
    expect(remote.puts, isEmpty);
    expect(_text(t, 'detail'), contains('Could not encode'));
  });

  testWidgets('a failed upload keeps the button and shows why', (t) async {
    final remote = _ReadOnlyRemote()
      ..files[kChallengePath] = jsonEncode(_challengeJson);
    await t.pumpWidget(_app(_screen(remote: remote)));
    await t.pump();
    await t.tap(find.byKey(const Key('take-photo')));
    await t.pump();
    expect(_text(t, 'detail'), contains('offline'));
    expect(find.byKey(const Key('take-photo')), findsOneWidget);
  });

  testWidgets('returning from Settings re-reads the challenge', (t) async {
    installFakeSecureStorage();
    final remote = MemRemote();
    await t.pumpWidget(_app(_screen(remote: remote)));
    await t.pump();
    expect(_text(t, 'headline'), 'Nothing due');
    remote.files[kChallengePath] = jsonEncode(_challengeJson);
    await t.tap(find.byIcon(Icons.settings));
    await t.pump();
    await t.pump(const Duration(seconds: 1));
    expect(find.text('Sync settings'), findsOneWidget);
    await t.pageBack();
    await t.pump();
    await t.pump(const Duration(seconds: 1));
    expect(_text(t, 'headline'), 'desk');
  });

  testWidgets('a failed fetch shows the error and a retry', (t) async {
    final remote = MemRemote()
      ..files[kChallengePath] = jsonEncode(_challengeJson);
    var broken = true;
    await t.pumpWidget(
      _app(
        HomeScreen(
          deviceId: 'p',
          sync: ChallengeSync(
            openClient: () async => broken ? BrokenRemote() : remote,
            clock: _today,
          ),
          clock: _today,
        ),
      ),
    );
    await t.pump();
    expect(_text(t, 'headline'), 'Could not reach the PC');
    broken = false;
    await t.tap(find.byKey(const Key('refresh')));
    await t.pump();
    expect(_text(t, 'headline'), 'desk');
  });
}
