// coverage:ignore-file
// Bootstrap only: the two calls below reach platform channels that
// `flutter test` has no binding for. Everything they wire is tested through
// HomeScreen's injectable seams.
import 'package:flutter/material.dart';
import 'package:home_guard_app/screens/home_screen.dart';
import 'package:home_guard_app/services/device_id.dart';
import 'package:home_guard_app/services/session_files.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/ui/theme.dart';

/// Entry point.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Minted once per install, before anything can stamp an upload with it.
  final deviceId = await initDeviceId();
  runApp(HomeGuardApp(deviceId: deviceId));
}

/// Root application widget.
class HomeGuardApp extends StatelessWidget {
  /// Creates the app for this install's [deviceId].
  const HomeGuardApp({required this.deviceId, super.key});

  /// This install's persisted device id.
  final String deviceId;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'home-guard',
      theme: buildAppTheme(),
      home: HomeScreen(
        deviceId: deviceId,
        store: SessionStore(PathProviderSessionFiles()),
      ),
    );
  }
}
