/// The zone rotation, as a forward-only edit history shared with the PC.
library;

/// One `effective_from` edit of the rotation.
///
/// Mirrors `home_guard/_zone_list.py::ZoneListEntry` exactly, including the
/// wire keys (`zones`, `t`), because both sides parse the *same* payload --
/// the whole history, not just the current list, so a merge is a dict union.
class ZoneListEntry {
  /// Creates an entry.
  const ZoneListEntry({
    required this.effectiveFrom,
    required this.zones,
    required this.editedAt,
  });

  /// `YYYY-MM-DD`. This list is in force from this day onward.
  final String effectiveFrom;

  /// The rotation, in order.
  final List<String> zones;

  /// Full ISO timestamp of the edit. Load-bearing: it is what resolves a
  /// same-day collision during a merge, so it must never be recomputed when
  /// an entry is merely copied around.
  final String editedAt;
}

/// The whole history: parse, serialise and merge.
///
/// Every rule here is the twin of `home_guard/_zone_merge.py`. They must
/// agree, because either device may run the merge and both must land on the
/// same result.
class ZoneHistory {
  /// Creates a history from [entries].
  const ZoneHistory(this.entries);

  /// Oldest first.
  final List<ZoneListEntry> entries;

  /// Schema version, matching `_zone_list._SCHEMA_VERSION`.
  static const int schemaVersion = 1;

  /// The rotation used when no history exists at all, matching
  /// `_constants.DEFAULT_ZONES`.
  static const List<String> defaultZones = [
    'desk',
    'kitchen counter',
    'entryway',
  ];

  /// Parses `{"v": 1, "e": {day: {"zones": [...], "t": iso}}}`.
  ///
  /// Returns null for anything that is not a history -- distinct from an
  /// empty history, so a caller can tell "could not read it" from "read it,
  /// there are no edits".
  static ZoneHistory? fromJson(Object? json) {
    if (json is! Map<String, Object?>) return null;
    final raw = json['e'];
    if (raw is! Map<String, Object?>) return null;
    final parsed = <ZoneListEntry>[];
    for (final entry in raw.entries) {
      final value = entry.value;
      if (value is! Map<String, Object?>) continue;
      final zones = value['zones'];
      final editedAt = value['t'];
      if (zones is! List || editedAt is! String) continue;
      final names = zones.whereType<String>().where((z) => z.trim().isNotEmpty);
      if (names.isEmpty) continue;
      parsed.add(
        ZoneListEntry(
          effectiveFrom: entry.key,
          zones: names.toList(),
          editedAt: editedAt,
        ),
      );
    }
    parsed.sort((a, b) => a.effectiveFrom.compareTo(b.effectiveFrom));
    return ZoneHistory(parsed);
  }

  /// Serialises back to the shared shape.
  Map<String, Object?> toJson() => {
    'v': schemaVersion,
    'e': {
      for (final e in entries)
        e.effectiveFrom: {'zones': e.zones, 't': e.editedAt},
    },
  };

  /// The rotation in force on [day]; the newest entry at or before it wins.
  List<String> zonesForDay(String day) {
    ZoneListEntry? best;
    for (final e in entries) {
      if (e.effectiveFrom.compareTo(day) <= 0) {
        if (best == null || e.effectiveFrom.compareTo(best.effectiveFrom) > 0) {
          best = e;
        }
      }
    }
    return best?.zones ?? defaultZones;
  }

  static Map<String, ZoneListEntry> _byDay(List<ZoneListEntry> entries) {
    final indexed = <String, ZoneListEntry>{};
    for (final e in entries) {
      final existing = indexed[e.effectiveFrom];
      if (existing == null || e.editedAt.compareTo(existing.editedAt) > 0) {
        indexed[e.effectiveFrom] = e;
      }
    }
    return indexed;
  }

  /// Merges [remote] into this history. See `_zone_merge.py` for the rules.
  ///
  /// [today] is a local `YYYY-MM-DD`. A remote entry for a past day may not
  /// *replace* a local one -- the history is forward-only so that editing the
  /// rotation cannot retroactively change which zone an already-judged past
  /// slot was checked against. It IS accepted when there is no local entry
  /// for that day: filling a gap is how a freshly installed phone learns the
  /// PC's history at all, and only overwriting is a rewrite.
  ZoneHistory merge(ZoneHistory remote, {required String today}) {
    final merged = _byDay(entries);
    for (final entry in _byDay(remote.entries).entries) {
      final existing = merged[entry.key];
      if (entry.key.compareTo(today) < 0 && existing != null) continue;
      if (existing == null ||
          entry.value.editedAt.compareTo(existing.editedAt) > 0) {
        merged[entry.key] = entry.value;
      }
    }
    final out = merged.values.toList()
      ..sort((a, b) => a.effectiveFrom.compareTo(b.effectiveFrom));
    return ZoneHistory(out);
  }

  /// Returns a new history with [zones] taking effect on [today].
  ///
  /// Replaces any existing entry for the same day rather than duplicating
  /// it, matching `record_zone_list_change`.
  ZoneHistory withRotation(
    List<String> zones, {
    required String today,
    required DateTime now,
  }) {
    final kept = entries.where((e) => e.effectiveFrom != today).toList()
      ..add(
        ZoneListEntry(
          effectiveFrom: today,
          zones: zones,
          editedAt: now.toUtc().toIso8601String(),
        ),
      )
      ..sort((a, b) => a.effectiveFrom.compareTo(b.effectiveFrom));
    return ZoneHistory(kept);
  }
}
