import 'package:flutter/material.dart';
import 'package:home_guard_app/screens/zones_screen.dart';
import 'package:home_guard_app/services/firebase_backend.dart';
import 'package:home_guard_app/services/google_sign_in_backend.dart';
import 'package:sync_settings_ui/sync_settings_ui.dart';

/// Settings: only the shared Firebase "Sync settings" screen.
///
/// Firebase is the sole transport for this app, so there is no GitHub
/// mirror entry here, unlike the older siblings.
class SettingsScreen extends StatelessWidget {
  /// Creates a [SettingsScreen].
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            key: const Key('open-zones'),
            contentPadding: EdgeInsets.zero,
            title: const Text('Zones'),
            subtitle: const Text('The places you clean, in rotation order'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push<void>(
              MaterialPageRoute(builder: (_) => const ZonesScreen()),
            ),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Sync settings'),
            subtitle: const Text('Firebase sync'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push<void>(
              MaterialPageRoute(
                builder: (_) => SyncSettingsScreen(
                  accountLoader: loadAccount,
                  accountSaver: saveAccount,
                  accountClearer: clearAccount,
                  sessionProbe: isFirebaseConfigured,
                  firebaseFactory: openFirebase,
                  googleFirebaseFactory: openFirebaseWithGoogle,
                  googleAvailable: googleSignInSupported,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
