import 'package:flutter/material.dart';
import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/ui/theme.dart';

/// Where the home screen is in the capture flow.
enum HomePhase {
  /// Fetching the challenge.
  loading,

  /// Firebase is not set up on this device.
  notConfigured,

  /// The fetch failed.
  error,

  /// The PC has nothing published.
  noChallenge,

  /// Today's slot was already cleared.
  consumed,

  /// The published challenge is for another day.
  stale,

  /// A photo can be taken.
  ready,

  /// The camera is open.
  capturing,

  /// Encoding + uploading.
  uploading,

  /// Uploaded; waiting for the PC to drain the node.
  awaitingPc,

  /// The PC drained the node -- accepted.
  accepted,

  /// Uploaded but never confirmed within the poll window.
  unconfirmed,
}

/// The home screen's body: zone headline, status line, one button.
///
/// Stateless and fully driven by [phase] so every state is a plain widget
/// test with no timers. The only button that exists is the camera button
/// -- there is intentionally no "pick from gallery" anywhere.
class HomeBody extends StatelessWidget {
  /// Creates the body.
  const HomeBody({
    required this.phase,
    required this.challenge,
    required this.detail,
    required this.onTakePhoto,
    required this.onRefresh,
    required this.onOpenSettings,
    super.key,
  });

  /// Current phase.
  final HomePhase phase;

  /// The last challenge read, if any.
  final Challenge? challenge;

  /// Status detail for the current phase.
  final String detail;

  /// Opens the camera.
  final VoidCallback onTakePhoto;

  /// Re-reads the challenge.
  final VoidCallback onRefresh;

  /// Opens the sync settings.
  final VoidCallback onOpenSettings;

  bool get _busy =>
      phase == HomePhase.loading ||
      phase == HomePhase.capturing ||
      phase == HomePhase.uploading ||
      phase == HomePhase.awaitingPc;

  String _headline() => switch (phase) {
    HomePhase.loading => 'Checking with the PC…',
    HomePhase.notConfigured => 'Not connected',
    HomePhase.error => 'Could not reach the PC',
    HomePhase.noChallenge => 'Nothing due',
    HomePhase.consumed => 'Done for today',
    HomePhase.stale => 'Nothing due yet',
    HomePhase.ready ||
    HomePhase.capturing ||
    HomePhase.uploading ||
    HomePhase.awaitingPc ||
    HomePhase.accepted ||
    HomePhase.unconfirmed => challenge?.zone ?? '',
  };

  String _hint() => switch (phase) {
    HomePhase.ready => 'Clear it, then take one photo of it.',
    HomePhase.capturing => 'Camera open…',
    HomePhase.uploading => 'Uploading…',
    HomePhase.awaitingPc => 'Waiting for the PC to accept…',
    HomePhase.noChallenge =>
      'The PC publishes a zone when a slot is due; nothing is due now.',
    _ => '',
  };

  Color _statusColor(BuildContext context) {
    final status = Theme.of(context).extension<AppStatusColors>()!;
    return switch (phase) {
      HomePhase.accepted || HomePhase.consumed => status.success,
      HomePhase.error ||
      HomePhase.notConfigured => Theme.of(context).colorScheme.error,
      HomePhase.unconfirmed || HomePhase.stale => status.warning,
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
          const Spacer(),
          Text(
            _headline(),
            key: const Key('headline'),
            textAlign: TextAlign.center,
            style: text.displaySmall,
          ),
          const SizedBox(height: 8),
          Text(_hint(), textAlign: TextAlign.center, style: text.bodyLarge),
          const SizedBox(height: 16),
          Text(
            detail,
            key: const Key('detail'),
            textAlign: TextAlign.center,
            style: text.bodyMedium?.copyWith(color: _statusColor(context)),
          ),
          const Spacer(),
          if (_busy) const LinearProgressIndicator(),
          if (phase == HomePhase.ready ||
              phase == HomePhase.capturing ||
              phase == HomePhase.uploading ||
              phase == HomePhase.awaitingPc ||
              phase == HomePhase.unconfirmed)
            FilledButton.icon(
              key: const Key('take-photo'),
              onPressed: _busy ? null : onTakePhoto,
              icon: const Icon(Icons.photo_camera),
              label: Text('Take photo of ${challenge?.zone ?? "zone"}'),
            ),
          if (phase == HomePhase.notConfigured)
            FilledButton(
              key: const Key('open-settings'),
              onPressed: onOpenSettings,
              child: const Text('Connect Firebase'),
            ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            key: const Key('refresh'),
            onPressed: _busy ? null : onRefresh,
            icon: const Icon(Icons.refresh),
            label: const Text('Check again'),
          ),
        ],
      ),
    );
  }
}
