import 'package:flutter/material.dart';
import 'package:home_guard_app/ui/theme.dart';

/// The zones screen's status note, shown as an icon (kuhy's textgate rule).
/// The old sentence is kept as the spoken label only.
enum ZoneCue {
  /// Up to date with the PC.
  synced,

  /// The last rotation seen; the PC is offline.
  cached,

  /// No rotation yet; these are the built-in defaults.
  fallback,

  /// A change is being saved.
  saving,

  /// Saved and sent to the PC.
  sent,

  /// Saved on this phone only, for now.
  savedLocal,

  /// Refused: a rotation needs at least one zone.
  needOne,
}

/// [cue] as one small coloured glyph (or a spinner while saving).
class ZoneCueIcon extends StatelessWidget {
  /// Creates the icon.
  const ZoneCueIcon(this.cue, {super.key});

  /// The note to show.
  final ZoneCue cue;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final status = Theme.of(context).extension<AppStatusColors>();
    final ok = status?.success ?? scheme.primary;
    final warn = status?.warning ?? scheme.tertiary;
    final key = Key('zones-cue-${cue.name}');
    final (IconData? icon, colour, spoken) = switch (cue) {
      ZoneCue.synced => (Icons.check, ok, 'Up to date with the PC.'),
      ZoneCue.cached => (
        Icons.history,
        scheme.onSurfaceVariant,
        'Showing the last rotation seen; the PC is offline.',
      ),
      ZoneCue.fallback => (
        Icons.settings_backup_restore,
        warn,
        'No rotation yet — these are the defaults.',
      ),
      ZoneCue.sent => (Icons.check_circle, ok, 'Saved and sent to the PC.'),
      ZoneCue.savedLocal => (
        Icons.phone_android,
        warn,
        'Saved on this phone. It will reach the PC when you have signal.',
      ),
      ZoneCue.needOne => (
        Icons.block,
        scheme.error,
        'A rotation needs at least one zone.',
      ),
      ZoneCue.saving => (null, scheme.primary, 'Saving'),
    };
    if (icon == null) {
      return Semantics(
        key: key,
        label: spoken,
        child: const SizedBox.square(
          dimension: 18,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }
    return Icon(icon, key: key, size: 18, color: colour, semanticLabel: spoken);
  }
}
