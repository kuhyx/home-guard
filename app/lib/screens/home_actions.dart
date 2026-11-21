import 'dart:async';

import 'package:crdt_sync_flutter/crdt_sync_flutter.dart';
import 'package:home_guard_app/services/e2e_sync.dart';
import 'package:material_ui/material_ui.dart';

/// The home screen's icon-only AppBar actions: E2E lock, recheck, settings.
///
/// Split out of `home_screen.dart` to keep it under the 250-line cap; the
/// screen still owns what each button does.
List<Widget> homeAppBarActions({
  required Future<void> Function() onRefresh,
  required Future<void> Function() onOpenSettings,
}) => [
  // Icon-only E2E state: closed lock when this device has no (or the wrong)
  // crdt-sync passphrase; tap to enter it, then recheck.
  ValueListenableBuilder<bool>(
    valueListenable: e2eLocked,
    builder: (_, locked, _) => E2ePassphraseButton(
      key: const Key('home-e2e'),
      locked: locked,
      onSaved: () => unawaited(onRefresh()),
    ),
  ),
  IconButton(
    key: const Key('home-recheck'),
    icon: const Icon(Icons.refresh, semanticLabel: 'Check the PC again'),
    onPressed: onRefresh,
  ),
  IconButton(
    key: const Key('home-settings'),
    icon: const Icon(Icons.settings, semanticLabel: 'Settings'),
    onPressed: onOpenSettings,
  ),
];
