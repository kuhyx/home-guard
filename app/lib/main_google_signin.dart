// coverage:ignore-file
// Autodrive entrypoint: jump straight into the Google one-tap sign-in on
// launch, so a deploy with `--target lib/main_google_signin.dart` can be
// driven end-to-end over adb. The Flutter tree is invisible to uiautomator,
// but the Credential Manager account picker this triggers is a native sheet,
// so the one tap that matters can be found by text and tapped. Same package,
// same keystore, same secure-storage session -- redeploying the normal
// entrypoint afterwards keeps the sign-in.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:home_guard_app/services/firebase_backend.dart';
import 'package:home_guard_app/ui/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const _SignInProbe());
}

class _SignInProbe extends StatefulWidget {
  const _SignInProbe();

  @override
  State<_SignInProbe> createState() => _SignInProbeState();
}

class _SignInProbeState extends State<_SignInProbe> {
  String _status = 'probe: starting Google sign-in…';

  // Flutter text is invisible to uiautomator, so the verdict also goes to
  // logcat (`I/flutter`), where the driving script reads it.
  void _report(String status) {
    debugPrint(status);
    if (mounted) setState(() => _status = status);
  }

  @override
  void initState() {
    super.initState();
    unawaited(_run());
  }

  Future<void> _run() async {
    if (await isFirebaseConfigured()) {
      _report('probe: ALREADY SIGNED IN');
      return;
    }
    try {
      final client = await openFirebaseWithGoogle();
      if (!mounted) return;
      if (client == null) {
        _report(
          'probe: CANCELLED (picker dismissed or sign-in unavailable -- '
          'see logcat GoogleSignIn)',
        );
        return;
      }
      final ok = await client.canAccessRemote();
      if (!mounted) return;
      _report(
        ok
            ? 'probe: SIGNED IN, database readable'
            : 'probe: SIGNED IN but database read denied (wrong account?)',
      );
    } on Object catch (e) {
      if (!mounted) return;
      _report('probe: FAILED $e');
    }
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    theme: buildAppTheme(),
    home: Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_status, textAlign: TextAlign.center),
        ),
      ),
    ),
  );
}
