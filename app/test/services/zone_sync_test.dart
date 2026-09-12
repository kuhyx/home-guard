import 'dart:convert';

import 'package:crdt_sync/crdt_sync.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/zone_history.dart';
import 'package:home_guard_app/services/zone_sync.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../fake_remote_store.dart';

final _now = DateTime.utc(2026, 9, 12, 19);
const _today = '2026-09-12';

/// A remote whose every call throws, i.e. airplane mode.
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

ZoneSync _sync({RemoteStore? remote}) => ZoneSync(
  openClient: () async => remote,
  prefs: SharedPreferences.getInstance,
  clock: () => _now,
);

String _payload(List<String> zones, String t) => jsonEncode({
  'v': 1,
  'e': {
    _today: {'zones': zones, 't': t},
  },
});

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('load', () {
    test('merges the PC history and caches it', () async {
      final remote = MemRemote()
        ..files[kZonesPath] = _payload(['mirror', 'toilet'], 'T1');
      final read = await _sync(remote: remote).load();
      expect(read.source, ZoneSource.synced);
      expect(read.zonesForDay(_today), ['mirror', 'toilet']);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString(kZoneCacheKey), isNotNull);
    });

    test('falls back to the cache when the PC is unreachable', () async {
      final remote = MemRemote()
        ..files[kZonesPath] = _payload(['mirror'], 'T1');
      await _sync(remote: remote).load();

      final read = await _sync(remote: _BrokenRemote()).load();
      expect(read.source, ZoneSource.cached);
      expect(read.zonesForDay(_today), ['mirror']);
    });

    test('falls back to the defaults with no cache and no network', () async {
      final read = await _sync(remote: _BrokenRemote()).load();
      expect(read.source, ZoneSource.fallback);
      expect(read.zonesForDay(_today), ZoneHistory.defaultZones);
    });

    test('an unconfigured Firebase is not a crash', () async {
      final read = await _sync().load();
      expect(read.source, ZoneSource.fallback);
    });

    test('a corrupt cache is ignored rather than fatal', () async {
      SharedPreferences.setMockInitialValues({kZoneCacheKey: '{not json'});
      final read = await _sync(remote: _BrokenRemote()).load();
      expect(read.source, ZoneSource.fallback);
    });

    test('an unreadable remote payload is treated as no remote', () async {
      final remote = MemRemote()..files[kZonesPath] = '["not", "a", "history"]';
      final read = await _sync(remote: remote).load();
      expect(read.source, ZoneSource.fallback);
    });
  });

  group('setZones', () {
    test('caches and publishes the new rotation', () async {
      final remote = MemRemote();
      expect(await _sync(remote: remote).setZones(['mirror']), isTrue);
      expect(remote.puts, [kZonesPath]);

      final published = ZoneHistory.fromJson(
        jsonDecode(remote.files[kZonesPath]!),
      );
      expect(published!.zonesForDay(_today), ['mirror']);
    });

    test(
      'an offline edit survives in the cache and reports the failure',
      () async {
        expect(
          await _sync(remote: _BrokenRemote()).setZones(['mirror']),
          isFalse,
        );

        // The edit must NOT be lost just because there was no signal.
        final read = await _sync(remote: _BrokenRemote()).load();
        expect(read.zonesForDay(_today), ['mirror']);
      },
    );

    test('an offline edit is pushed by the next successful publish', () async {
      await _sync(remote: _BrokenRemote()).setZones(['mirror']);
      final remote = MemRemote();
      await _sync(remote: remote).setZones(['mirror', 'washbasin']);
      final published = ZoneHistory.fromJson(
        jsonDecode(remote.files[kZonesPath]!),
      );
      expect(published!.zonesForDay(_today), ['mirror', 'washbasin']);
    });

    test('editing twice in one day replaces, never duplicates', () async {
      final remote = MemRemote();
      final sync = _sync(remote: remote);
      await sync.setZones(['mirror']);
      await sync.setZones(['toilet']);
      final published = ZoneHistory.fromJson(
        jsonDecode(remote.files[kZonesPath]!),
      );
      expect(published!.entries.length, 1);
      expect(published.zonesForDay(_today), ['toilet']);
    });

    test('a past entry from the PC survives a local edit', () async {
      final remote = MemRemote()
        ..files[kZonesPath] = jsonEncode({
          'v': 1,
          'e': {
            '2026-09-01': {
              'zones': ['old'],
              't': 'T0',
            },
          },
        });
      await _sync(remote: remote).load();
      await _sync(remote: remote).setZones(['mirror']);
      final published = ZoneHistory.fromJson(
        jsonDecode(remote.files[kZonesPath]!),
      );
      expect(published!.zonesForDay('2026-09-05'), ['old']);
      expect(published.zonesForDay(_today), ['mirror']);
    });
  });
}
