import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/ui/theme.dart';

void main() {
  test('theme carries the shared status colours', () {
    final theme = buildAppTheme();
    expect(theme.extension<AppStatusColors>(), AppStatusColors.dark);
    expect(theme.colorScheme.surface, const Color(0xFF211D1B));
  });

  test('status colours copy and lerp like any ThemeExtension', () {
    const a = AppStatusColors.dark;
    final b = a.copyWith(success: const Color(0xFF000000));
    expect(b.success, const Color(0xFF000000));
    expect(b.warning, a.warning);
    expect(a.copyWith().success, a.success);
    expect(a.lerp(null, 0.5), a);
    expect(a.lerp(b, 1).success, const Color(0xFF000000));
  });
}
