import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/screens/settings_screen.dart';
import 'package:sync_settings_ui/sync_settings_ui.dart';

import 'fake_secure_storage.dart';

void main() {
  testWidgets('has only the shared Firebase sync entry, and opens it', (
    tester,
  ) async {
    installFakeSecureStorage();
    await tester.pumpWidget(const MaterialApp(home: SettingsScreen()));

    expect(find.text('Sync settings'), findsOneWidget);
    // Firebase-only app: no GitHub mirror entry, by rule.
    expect(find.textContaining('GitHub'), findsNothing);

    await tester.tap(find.text('Sync settings'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.byType(SyncSettingsScreen), findsOneWidget);
  });
}
