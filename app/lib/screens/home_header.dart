import 'package:flutter/material.dart';
import 'package:home_guard_app/screens/home_body.dart' show HomePhase;
import 'package:home_guard_app/screens/home_cue.dart';
import 'package:home_guard_app/ui/theme.dart';

/// The top of the home screen: headline glyph or zone name, photo tally,
/// status cue and the PC's assigned zone. No painted words except the
/// user's own zone names; the old sentences are spoken labels only.
class HomeHeader extends StatelessWidget {
  /// Creates the header.
  const HomeHeader({
    required this.phase,
    required this.selectedZone,
    required this.photoCount,
    required this.cue,
    required this.assignedZone,
    super.key,
  });

  /// Current phase.
  final HomePhase phase;

  /// The zone being cleaned.
  final String? selectedZone;

  /// How many photos this clean has so far.
  final int photoCount;

  /// Status note, as an icon.
  final HomeCue cue;

  /// The zone the PC is waiting on, when it has said.
  final String? assignedZone;

  /// The big glyph for phases that have no zone to show, with its colour and
  /// spoken label (the old headline sentence).
  (IconData, Color, String)? _phaseGlyph(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final status = Theme.of(context).extension<AppStatusColors>()!;
    return switch (phase) {
      HomePhase.notConfigured => (
        Icons.link_off,
        scheme.error,
        'Not connected',
      ),
      HomePhase.accepted => (
        Icons.check_circle,
        status.success,
        'Done — the PC took it',
      ),
      HomePhase.savedOffline => (
        Icons.save,
        status.warning,
        'Saved on this phone',
      ),
      HomePhase.uploading => (
        Icons.cloud_upload,
        scheme.onSurfaceVariant,
        'Sending to the PC',
      ),
      _ when selectedZone == null => (
        Icons.touch_app,
        scheme.onSurfaceVariant,
        'Pick a place',
      ),
      _ => null,
    };
  }

  Widget _headline(BuildContext context) {
    final glyph = _phaseGlyph(context);
    if (glyph != null) {
      final (icon, colour, spoken) = glyph;
      return Icon(
        icon,
        key: Key('headline-${phase.name}'),
        size: 64,
        color: colour,
        semanticLabel: spoken,
      );
    }
    if (phase == HomePhase.loading) return const SizedBox(height: 64);
    // The zone name is the user's own content, so it may stay a word.
    return Text(
      selectedZone!,
      key: const Key('headline'),
      textAlign: TextAlign.center,
      style: Theme.of(context).textTheme.displaySmall,
    );
  }

  /// Camera glyph plus the shot count, once there is at least one.
  Widget _photoTally(BuildContext context) {
    if (phase != HomePhase.ready || photoCount == 0) {
      return const SizedBox(height: 24);
    }
    return Semantics(
      label: '$photoCount photo${photoCount == 1 ? '' : 's'} so far',
      excludeSemantics: true,
      child: Row(
        key: const Key('photo-tally'),
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.photo_camera, size: 20),
          const SizedBox(width: 6),
          Text('$photoCount', style: Theme.of(context).textTheme.titleLarge),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final assigned = assignedZone;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 8),
        Center(child: _headline(context)),
        const SizedBox(height: 8),
        _photoTally(context),
        const SizedBox(height: 12),
        Center(child: CueIcon(cue)),
        const SizedBox(height: 16),
        if (assigned != null && phase == HomePhase.ready)
          Semantics(
            label: 'The PC is waiting on $assigned',
            excludeSemantics: true,
            child: Row(
              key: const Key('assigned'),
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.computer, size: 18),
                const SizedBox(width: 6),
                Text(assigned, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
      ],
    );
  }
}
