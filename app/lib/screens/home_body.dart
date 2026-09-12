import 'package:flutter/material.dart';
import 'package:home_guard_app/ui/theme.dart';

/// Where the home screen is in the capture flow.
///
/// Note what is *absent*: there is no longer a phase meaning "the PC has
/// published nothing, so you cannot do anything". Cleaning is something you
/// do with your hands; the PC not being switched on is not a reason the app
/// should refuse to record it.
enum HomePhase {
  /// Loading the rotation.
  loading,

  /// Firebase is not set up on this device.
  notConfigured,

  /// Ready to photograph the chosen zone.
  ready,

  /// The camera is open.
  capturing,

  /// Sending to the PC.
  uploading,

  /// The PC took it.
  accepted,

  /// Saved on this phone; it will go to the PC later.
  savedOffline,
}

/// The home screen's body: pick a zone, photograph it, finish.
///
/// Stateless and fully driven by its inputs, so every state is a plain
/// widget test with no timers.
class HomeBody extends StatelessWidget {
  /// Creates the body.
  const HomeBody({
    required this.phase,
    required this.zones,
    required this.selectedZone,
    required this.photoCount,
    required this.detail,
    required this.assignedZone,
    required this.onZoneSelected,
    required this.onTakePhoto,
    required this.onFinish,
    required this.onOpenSettings,
    required this.onOpenHistory,
    super.key,
  });

  /// Current phase.
  final HomePhase phase;

  /// The rotation, from the local cache when the PC is unreachable.
  final List<String> zones;

  /// The zone being cleaned.
  final String? selectedZone;

  /// How many photos this clean has so far.
  final int photoCount;

  /// Status detail for the current phase.
  final String detail;

  /// The zone the PC is waiting on, when it has said. Decoration only --
  /// never a precondition for the camera.
  final String? assignedZone;

  /// Called when a different zone is chosen.
  final ValueChanged<String> onZoneSelected;

  /// Opens the camera for one more photo.
  final VoidCallback onTakePhoto;

  /// Finishes the clean and tries to send it.
  final VoidCallback onFinish;

  /// Opens the sync settings.
  final VoidCallback onOpenSettings;

  /// Opens the list of past cleans.
  final VoidCallback onOpenHistory;

  bool get _busy =>
      phase == HomePhase.loading ||
      phase == HomePhase.capturing ||
      phase == HomePhase.uploading;

  String _headline() => switch (phase) {
    HomePhase.loading => 'Loading…',
    HomePhase.notConfigured => 'Not connected',
    HomePhase.accepted => 'Done — the PC took it',
    HomePhase.savedOffline => 'Saved on this phone',
    _ => selectedZone ?? 'Pick a place',
  };

  String _hint() => switch (phase) {
    HomePhase.ready when photoCount == 0 =>
      'Clean it, then take as many photos as it takes.',
    HomePhase.ready => '$photoCount photo${photoCount == 1 ? '' : 's'} so far.',
    HomePhase.capturing => 'Camera open…',
    HomePhase.uploading => 'Sending to the PC…',
    _ => '',
  };

  Color _statusColor(BuildContext context) {
    final status = Theme.of(context).extension<AppStatusColors>()!;
    return switch (phase) {
      HomePhase.accepted => status.success,
      HomePhase.savedOffline => status.warning,
      HomePhase.notConfigured => Theme.of(context).colorScheme.error,
      _ => Theme.of(context).colorScheme.onSurfaceVariant,
    };
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 8),
          Text(
            _headline(),
            key: const Key('headline'),
            textAlign: TextAlign.center,
            style: text.displaySmall,
          ),
          const SizedBox(height: 8),
          Text(_hint(), textAlign: TextAlign.center, style: text.bodyLarge),
          const SizedBox(height: 12),
          Text(
            detail,
            key: const Key('detail'),
            textAlign: TextAlign.center,
            style: text.bodyMedium?.copyWith(color: _statusColor(context)),
          ),
          const SizedBox(height: 16),
          if (assignedZone != null && phase == HomePhase.ready)
            Text(
              'The PC is waiting on $assignedZone',
              key: const Key('assigned'),
              textAlign: TextAlign.center,
              style: text.bodySmall,
            ),
          Expanded(child: _zonePicker(context)),
          if (_busy) const LinearProgressIndicator(),
          const SizedBox(height: 8),
          if (phase == HomePhase.ready)
            FilledButton.icon(
              key: const Key('take-photo'),
              onPressed: _busy || selectedZone == null ? null : onTakePhoto,
              icon: const Icon(Icons.photo_camera),
              label: Text(photoCount == 0 ? 'Take a photo' : 'Another photo'),
            ),
          if (phase == HomePhase.ready && photoCount > 0) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('finish'),
              onPressed: _busy ? null : onFinish,
              icon: const Icon(Icons.check),
              label: Text('Done — $photoCount photo'
                  '${photoCount == 1 ? '' : 's'}'),
            ),
          ],
          if (phase == HomePhase.notConfigured)
            FilledButton(
              key: const Key('open-settings'),
              onPressed: onOpenSettings,
              child: const Text('Connect Firebase'),
            ),
          const SizedBox(height: 8),
          TextButton.icon(
            key: const Key('open-history'),
            onPressed: onOpenHistory,
            // Deliberately NOT Icons.photo_library: camera-only capture is
            // load-bearing security and a gallery icon anywhere in this app
            // is asserted against.
            icon: const Icon(Icons.history),
            label: const Text('Past cleans'),
          ),
        ],
      ),
    );
  }

  Widget _zonePicker(BuildContext context) {
    if (phase != HomePhase.ready || zones.isEmpty) {
      return const SizedBox.shrink();
    }
    return SingleChildScrollView(
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final zone in zones)
            ChoiceChip(
              key: Key('zone-$zone'),
              label: Text(zone),
              selected: zone == selectedZone,
              // Changing zone mid-clean would orphan the photos already
              // taken against the previous one.
              onSelected: photoCount > 0
                  ? null
                  : (_) => onZoneSelected(zone),
            ),
        ],
      ),
    );
  }
}
