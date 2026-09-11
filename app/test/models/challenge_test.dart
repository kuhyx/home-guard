import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/models/challenge.dart';

Map<String, Object?> _wire({bool consumed = false}) => {
  'day': '2026-09-11',
  'slot': '0800',
  'zone': 'kitchen counter',
  'token': 'tok-abc',
  'issued_at': '2026-09-11T08:00:00+02:00',
  'consumed': consumed,
};

void main() {
  group('Challenge.fromJson', () {
    test('parses the PC wire shape verbatim', () {
      final c = Challenge.fromJson(_wire())!;
      expect(c.day, '2026-09-11');
      expect(c.slot, '0800');
      expect(c.zone, 'kitchen counter');
      expect(c.token, 'tok-abc');
      expect(c.issuedAt, '2026-09-11T08:00:00+02:00');
      expect(c.consumed, isFalse);
    });

    test('rejects non-objects', () {
      expect(Challenge.fromJson(null), isNull);
      expect(Challenge.fromJson('x'), isNull);
      expect(Challenge.fromJson(<Object?>[]), isNull);
    });

    test('rejects a missing or mistyped field', () {
      for (final key in _wire().keys) {
        final missing = _wire()..remove(key);
        expect(Challenge.fromJson(missing), isNull, reason: 'missing $key');
        final wrong = _wire()..[key] = 42;
        expect(Challenge.fromJson(wrong), isNull, reason: 'mistyped $key');
      }
    });

    test('rejects blank identifying fields', () {
      for (final key in ['day', 'slot', 'zone', 'token']) {
        expect(Challenge.fromJson(_wire()..[key] = ''), isNull, reason: key);
      }
    });
  });

  group('dayOf', () {
    test('formats like the PC (%Y-%m-%d, zero-padded, local)', () {
      expect(Challenge.dayOf(DateTime(2026, 1, 5, 23, 59)), '2026-01-05');
    });
  });

  group('isSatisfiable', () {
    final today = DateTime(2026, 9, 11, 10);

    test('true for an unconsumed challenge minted today', () {
      expect(Challenge.fromJson(_wire())!.isSatisfiable(today), isTrue);
    });

    test('false once consumed', () {
      expect(
        Challenge.fromJson(_wire(consumed: true))!.isSatisfiable(today),
        isFalse,
      );
    });

    test('false for another day', () {
      expect(
        Challenge.fromJson(_wire())!.isSatisfiable(DateTime(2026, 9, 12)),
        isFalse,
      );
    });
  });
}
