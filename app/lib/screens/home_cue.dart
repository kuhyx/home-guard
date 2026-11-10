import 'package:flutter/material.dart';
import 'package:home_guard_app/ui/theme.dart';

/// One status note under the home headline, shown as an icon, never a
/// sentence (kuhy's textgate rule). The old sentence survives only as the
/// spoken label.
enum HomeCue {
  /// Nothing to say.
  none,

  /// Offline; the zones are the last rotation the PC sent.
  offlineCached,

  /// Offline and never synced; the zones are the built-in defaults.
  offlineDefault,

  /// The camera closed without a photo.
  noPhoto,

  /// The photo could not be re-encoded under the upload cap.
  badPhoto,

  /// The PC recorded the clean.
  recorded,

  /// The clean is queued on this phone for the PC.
  savedOffline,
}

/// The glyph, colour and spoken label for [cue], or null for [HomeCue.none].
(IconData, Color, String)? cueLook(BuildContext context, HomeCue cue) {
  final scheme = Theme.of(context).colorScheme;
  final status = Theme.of(context).extension<AppStatusColors>()!;
  return switch (cue) {
    HomeCue.none => null,
    HomeCue.offlineCached => (
      Icons.cloud_off,
      scheme.onSurfaceVariant,
      'Offline — using the last rotation the PC sent.',
    ),
    HomeCue.offlineDefault => (
      Icons.settings_backup_restore,
      status.warning,
      'Offline — using the default rotation.',
    ),
    HomeCue.noPhoto => (
      Icons.no_photography,
      status.warning,
      'No photo taken.',
    ),
    HomeCue.badPhoto => (
      Icons.broken_image,
      scheme.error,
      'Could not use that photo.',
    ),
    HomeCue.recorded => (
      Icons.cloud_done,
      status.success,
      'The PC recorded this clean.',
    ),
    HomeCue.savedOffline => (
      Icons.phone_android,
      status.warning,
      'Saved here. It will reach the PC next time both are on.',
    ),
  };
}

/// [cue] as a coloured icon; an empty box for [HomeCue.none].
class CueIcon extends StatelessWidget {
  /// Creates the icon.
  const CueIcon(this.cue, {super.key});

  /// The note to show.
  final HomeCue cue;

  @override
  Widget build(BuildContext context) {
    final look = cueLook(context, cue);
    if (look == null) return const SizedBox(height: 32);
    final (icon, colour, spoken) = look;
    return Icon(
      icon,
      key: Key('cue-${cue.name}'),
      size: 32,
      color: colour,
      semanticLabel: spoken,
    );
  }
}
