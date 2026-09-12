/// Reads, edits and publishes the zone rotation, offline-first.
///
/// The rotation is the one piece of PC state the phone needs *before* it can
/// do anything useful, so it is cached locally and every read falls back to
/// that cache. An edit applies to the cache immediately and is published on a
/// best-effort basis: losing the network must never lose the edit, and must
/// never stop you picking a zone to clean.
library;

import 'dart:convert';

import 'package:crdt_sync/crdt_sync.dart';
import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/models/zone_history.dart';
import 'package:home_guard_app/services/firebase_backend.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// RTDB path, identical to `home_guard/_constants.py::SYNC_ZONES_PATH`.
const kZonesPath = 'home-guard-sync/zones/current.json';

/// SharedPreferences key for the cached history.
const kZoneCacheKey = 'home_guard.zones';

/// Where a rotation came from, so the UI can be honest about staleness.
enum ZoneSource {
  /// Freshly merged with the PC's published history.
  synced,

  /// The local cache; the PC could not be reached.
  cached,

  /// Nothing cached and no network: `ZoneHistory.defaultZones`.
  fallback,
}

/// A rotation read, with its provenance.
class ZoneRead {
  /// Creates a read result.
  const ZoneRead(this.history, this.source);

  /// The history, never null -- an empty one still resolves to the defaults.
  final ZoneHistory history;

  /// Where it came from.
  final ZoneSource source;

  /// Today's rotation.
  List<String> zonesForDay(String day) => history.zonesForDay(day);
}

/// Offline-first zone rotation storage and sync.
class ZoneSync {
  /// Creates a syncer; every collaborator is injectable for tests.
  ZoneSync({
    Future<RemoteStore?> Function()? openClient,
    Future<SharedPreferences> Function()? prefs,
    DateTime Function()? clock,
  }) : _openClient = openClient ?? openFirebase,
       _prefs = prefs ?? SharedPreferences.getInstance,
       _clock = clock ?? DateTime.now;

  final Future<RemoteStore?> Function() _openClient;
  final Future<SharedPreferences> Function() _prefs;
  final DateTime Function() _clock;

  /// The local calendar day, formatted the way the PC formats `day`.
  ///
  /// Local, never UTC: `_gate.py` derives its day with `.astimezone()`, and a
  /// rotation edit bucketed under a different date than the gate reads would
  /// silently apply a day late.
  String today() => Challenge.dayOf(_clock());

  Future<ZoneHistory?> _readCache() async {
    final store = await _prefs();
    final text = store.getString(kZoneCacheKey);
    if (text == null || text.isEmpty) return null;
    try {
      return ZoneHistory.fromJson(jsonDecode(text));
    } on FormatException {
      return null;
    }
  }

  Future<void> _writeCache(ZoneHistory history) async {
    final store = await _prefs();
    await store.setString(kZoneCacheKey, jsonEncode(history.toJson()));
  }

  Future<ZoneHistory?> _fetchRemote() async {
    final client = await _open();
    if (client == null) return null;
    try {
      final text = await client.getFileText(kZonesPath);
      if (text == null || text.isEmpty) return null;
      return ZoneHistory.fromJson(jsonDecode(text));
    } on Exception {
      return null;
    }
  }

  /// Loads the rotation: remote merged into cache, else cache, else defaults.
  ///
  /// Never throws and never blocks on the network beyond one failed call --
  /// with the PC off this returns the cache, which is the whole point.
  Future<ZoneRead> load() async {
    final today = this.today();
    final cached = await _readCache();
    final remote = await _fetchRemote();
    if (remote == null) {
      if (cached == null) {
        return const ZoneRead(ZoneHistory([]), ZoneSource.fallback);
      }
      return ZoneRead(cached, ZoneSource.cached);
    }
    final merged = (cached ?? const ZoneHistory([])).merge(
      remote,
      today: today,
    );
    await _writeCache(merged);
    return ZoneRead(merged, ZoneSource.synced);
  }

  /// Replaces the rotation with [zones], effective today.
  ///
  /// Writes the cache first and publishes second, so an edit made with no
  /// signal survives and is pushed by the next successful [load]/[setZones].
  /// Returns true when the publish also landed.
  Future<bool> setZones(List<String> zones) async {
    final now = _clock();
    final today = Challenge.dayOf(now);
    final base = await _readCache() ?? const ZoneHistory([]);
    final updated = base.withRotation(zones, today: today, now: now);
    await _writeCache(updated);
    return await _publish(updated);
  }

  Future<bool> _publish(ZoneHistory history) async {
    final client = await _open();
    if (client == null) return false;
    try {
      await client.putFileText(
        kZonesPath,
        jsonEncode(history.toJson()),
        message: 'home-guard: zone rotation from the phone',
      );
      return true;
    } on Exception {
      return false;
    }
  }

  Future<RemoteStore?> _open() async {
    try {
      return await _openClient();
    } on Object {
      return null;
    }
  }
}
