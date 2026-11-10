import 'package:design_system/design_system.dart' show FitGrid;
import 'package:flutter/material.dart';
import 'package:home_guard_app/screens/home_cue.dart';
import 'package:home_guard_app/screens/home_header.dart';

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
    required this.cue,
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

  /// Status note for the current phase, shown as an icon.
  final HomeCue cue;

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

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          HomeHeader(
            phase: phase,
            selectedZone: selectedZone,
            photoCount: photoCount,
            cue: cue,
            assignedZone: assignedZone,
          ),
          Expanded(child: _zonePicker(context)),
          if (_busy) const LinearProgressIndicator(),
          const SizedBox(height: 8),
          if (phase == HomePhase.ready)
            FilledButton(
              key: const Key('take-photo'),
              onPressed: _busy || selectedZone == null ? null : onTakePhoto,
              child: Icon(
                photoCount == 0 ? Icons.photo_camera : Icons.add_a_photo,
                semanticLabel: photoCount == 0
                    ? 'Take a photo'
                    : 'Another photo',
              ),
            ),
          if (phase == HomePhase.ready && photoCount > 0) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('finish'),
              onPressed: _busy ? null : onFinish,
              icon: const Icon(Icons.check),
              // The count is a number, not a word: it shows what "done"
              // will send.
              label: Text(
                '$photoCount',
                semanticsLabel:
                    'Done — $photoCount photo${photoCount == 1 ? '' : 's'}',
              ),
            ),
          ],
          if (phase == HomePhase.notConfigured)
            IconButton.filledTonal(
              key: const Key('open-settings'),
              onPressed: onOpenSettings,
              icon: const Icon(
                Icons.settings,
                semanticLabel: 'Connect Firebase',
              ),
            ),
          const SizedBox(height: 8),
          IconButton(
            key: const Key('open-history'),
            onPressed: onOpenHistory,
            // Deliberately NOT Icons.photo_library: camera-only capture is
            // load-bearing security and a gallery icon anywhere in this app
            // is asserted against.
            icon: const Icon(Icons.history, semanticLabel: 'Past cleans'),
          ),
        ],
      ),
    );
  }

  Widget _zonePicker(BuildContext context) {
    if (phase != HomePhase.ready || zones.isEmpty) {
      return const SizedBox.shrink();
    }
    return FitGrid(
      itemCount: zones.length,
      columns: 2,
      minSquare: 0.3,
      padding: EdgeInsets.zero,
      itemBuilder: (context, i) {
        final zone = zones[i];
        return SizedBox.expand(
          child: ChoiceChip(
            key: Key('zone-$zone'),
            label: Text(zone, maxLines: 1, overflow: TextOverflow.ellipsis),
            selected: zone == selectedZone,
            // Changing zone mid-clean would orphan the photos already
            // taken against the previous one.
            onSelected: photoCount > 0 ? null : (_) => onZoneSelected(zone),
          ),
        );
      },
    );
  }
}
