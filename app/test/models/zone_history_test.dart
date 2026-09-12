import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/zone_history.dart';

const today = '2026-09-12';

ZoneListEntry e(String day, List<String> zones, String t) =>
    ZoneListEntry(effectiveFrom: day, zones: zones, editedAt: t);

void main() {
  group('fromJson', () {
    test('parses the shared payload shape', () {
      final h = ZoneHistory.fromJson(
        jsonDecode('{"v":1,"e":{"$today":{"zones":["mirror"],"t":"T1"}}}'),
      );
      expect(h!.entries.single.zones, ['mirror']);
      expect(h.entries.single.effectiveFrom, today);
    });

    test('returns null for anything that is not a history', () {
      expect(ZoneHistory.fromJson(null), isNull);
      expect(ZoneHistory.fromJson('nope'), isNull);
      expect(ZoneHistory.fromJson(<String, Object?>{}), isNull);
      expect(ZoneHistory.fromJson(<String, Object?>{'e': 'nope'}), isNull);
    });

    test('an empty history is not the same as an unreadable one', () {
      expect(
        ZoneHistory.fromJson(jsonDecode('{"v":1,"e":{}}'))!.entries,
        <ZoneListEntry>[],
      );
    });

    test('skips malformed entries without discarding the good ones', () {
      final h = ZoneHistory.fromJson(
        jsonDecode(
          '{"v":1,"e":{"$today":{"zones":["ok"],"t":"T1"},'
          '"2026-09-13":{"zones":[],"t":"T2"},'
          '"2026-09-14":{"zones":["x"]},'
          '"2026-09-15":"garbage"}}',
        ),
      );
      expect(h!.entries.map((x) => x.effectiveFrom), [today]);
    });
  });

  test('toJson round-trips through fromJson', () {
    final original = ZoneHistory([
      e(today, ['mirror', 'toilet'], 'T1'),
    ]);
    final back = ZoneHistory.fromJson(
      jsonDecode(jsonEncode(original.toJson())),
    );
    expect(back!.entries.single.zones, ['mirror', 'toilet']);
    expect(back.entries.single.editedAt, 'T1');
  });

  group('zonesForDay', () {
    test('newest entry at or before the day wins', () {
      final h = ZoneHistory([
        e('2026-09-01', ['old'], 'T1'),
        e('2026-09-12', ['new'], 'T2'),
      ]);
      expect(h.zonesForDay('2026-09-11'), ['old']);
      expect(h.zonesForDay('2026-09-12'), ['new']);
    });

    test('falls back to the defaults with no applicable entry', () {
      expect(
        const ZoneHistory([]).zonesForDay(today),
        ZoneHistory.defaultZones,
      );
      final future = ZoneHistory([
        e('2099-01-01', ['later'], 'T1'),
      ]);
      expect(future.zonesForDay(today), ZoneHistory.defaultZones);
    });
  });

  group('merge — must agree with _zone_merge.py', () {
    test('disjoint days are unioned', () {
      final merged =
          ZoneHistory([
            e(today, ['desk'], 'T1'),
          ]).merge(
            ZoneHistory([
              e('2026-09-13', ['mirror'], 'T2'),
            ]),
            today: today,
          );
      expect(merged.entries.map((x) => x.effectiveFrom), [today, '2026-09-13']);
    });

    test('a same-day collision is won by the later edit', () {
      final merged =
          ZoneHistory([
            e(today, ['desk'], '2026-09-12T08:00:00Z'),
          ]).merge(
            ZoneHistory([
              e(today, ['mirror'], '2026-09-12T19:00:00Z'),
            ]),
            today: today,
          );
      expect(merged.entries.single.zones, ['mirror']);
    });

    test('local wins a same-day collision when it is newer', () {
      final merged =
          ZoneHistory([
            e(today, ['desk'], '2026-09-12T20:00:00Z'),
          ]).merge(
            ZoneHistory([
              e(today, ['mirror'], '2026-09-12T09:00:00Z'),
            ]),
            today: today,
          );
      expect(merged.entries.single.zones, ['desk']);
    });

    test('remote cannot rewrite the past, even with a newer timestamp', () {
      final local = ZoneHistory([
        e('2026-09-01', ['desk'], '2026-09-01T08:00:00Z'),
      ]);
      final merged = local.merge(
        ZoneHistory([
          e('2026-09-01', ['mirror'], '2099-01-01T00:00:00Z'),
        ]),
        today: today,
      );
      expect(merged.entries.single.zones, ['desk']);
    });

    test('a fresh device learns past entries it does not have', () {
      // Filling a gap is not a rewrite: rejecting every past remote entry
      // would leave a freshly installed phone permanently historyless.
      final merged = const ZoneHistory([]).merge(
        ZoneHistory([
          e('2026-09-01', ['old'], 'T0'),
        ]),
        today: today,
      );
      expect(merged.entries.single.zones, ['old']);
    });

    test('a past gap is filled without touching existing past entries', () {
      final merged =
          ZoneHistory([
            e('2026-09-05', ['kept'], '2026-09-05T08:00:00Z'),
          ]).merge(
            ZoneHistory([
              e('2026-09-01', ['learned'], '2026-09-01T08:00:00Z'),
              e('2026-09-05', ['rewrite'], '2099-01-01T00:00:00Z'),
            ]),
            today: today,
          );
      expect(merged.entries.map((x) => x.zones.single), ['learned', 'kept']);
    });

    test('duplicate days inside one history collapse to the later', () {
      final merged = const ZoneHistory([]).merge(
        ZoneHistory([
          e(today, ['old'], '2026-09-12T08:00:00Z'),
          e(today, ['new'], '2026-09-12T18:00:00Z'),
        ]),
        today: today,
      );
      expect(merged.entries.single.zones, ['new']);
    });

    test('is order-independent', () {
      final a = ZoneHistory([
        e(today, ['desk'], 'T1'),
      ]);
      final b = ZoneHistory([
        e('2026-09-13', ['mirror'], 'T2'),
      ]);
      List<String> days(ZoneHistory h) =>
          h.entries.map((x) => x.effectiveFrom).toList();
      expect(days(a.merge(b, today: today)), days(b.merge(a, today: today)));
    });
  });

  group('withRotation', () {
    test('adds an entry effective today', () {
      final h = const ZoneHistory([]).withRotation(
        ['mirror'],
        today: today,
        now: DateTime.utc(2026, 9, 12, 19),
      );
      expect(h.entries.single.effectiveFrom, today);
      expect(h.entries.single.zones, ['mirror']);
    });

    test('replaces a same-day entry rather than duplicating it', () {
      final h = ZoneHistory([
        e(today, ['desk'], 'T1'),
        e('2026-09-01', ['older'], 'T0'),
      ]).withRotation(['mirror'], today: today, now: DateTime.utc(2026, 9, 12));
      expect(h.entries.length, 2);
      expect(h.zonesForDay(today), ['mirror']);
      expect(h.zonesForDay('2026-09-05'), ['older']);
    });
  });

  group('reorder', () {
    const base = ['a', 'b', 'c', 'd'];

    test('moving an item down lands it at the requested index', () {
      expect(ZoneHistory.reorder(base, 0, 2), ['b', 'c', 'a', 'd']);
    });

    test('moving an item up lands it at the requested index', () {
      expect(ZoneHistory.reorder(base, 3, 1), ['a', 'd', 'b', 'c']);
    });

    test('moving to the end works', () {
      expect(ZoneHistory.reorder(base, 0, 3), ['b', 'c', 'd', 'a']);
    });

    test('moving to the start works', () {
      expect(ZoneHistory.reorder(base, 2, 0), ['c', 'a', 'b', 'd']);
    });

    test('a no-op move changes nothing', () {
      expect(ZoneHistory.reorder(base, 1, 1), base);
    });

    test('never loses or duplicates a zone, for any index pair', () {
      for (var from = 0; from < base.length; from++) {
        for (var to = 0; to < base.length; to++) {
          final out = ZoneHistory.reorder(base, from, to);
          expect(out.length, base.length, reason: 'from=$from to=$to');
          expect(out.toSet(), base.toSet(), reason: 'from=$from to=$to');
        }
      }
    });

    test('does not mutate its input', () {
      final input = ['a', 'b', 'c'];
      ZoneHistory.reorder(input, 0, 2);
      expect(input, ['a', 'b', 'c']);
    });
  });
}
