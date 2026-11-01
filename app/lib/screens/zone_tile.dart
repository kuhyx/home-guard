import 'dart:async';

import 'package:design_system/design_system.dart' show AppRadius, AppSpacing;
import 'package:flutter/material.dart';

/// One zone as a tile: tap the cross to remove, long-press for the order.
class ZoneTile extends StatelessWidget {
  /// Creates the tile.
  const ZoneTile({
    required this.name,
    required this.onRemove,
    required this.onMoveEarlier,
    required this.onMoveLater,
    super.key,
  });

  /// The zone's name.
  final String name;

  /// Removes the zone.
  final VoidCallback onRemove;

  /// Moves it earlier; null at the front.
  final VoidCallback? onMoveEarlier;

  /// Moves it later; null at the back.
  final VoidCallback? onMoveLater;

  Future<void> _sheet(BuildContext context) => showModalBottomSheet<void>(
    context: context,
    builder: (sheet) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(title: Text(name)),
          ListTile(
            key: const Key('move-earlier'),
            leading: const Icon(Icons.arrow_upward),
            title: const Text('Earlier in the rotation'),
            enabled: onMoveEarlier != null,
            onTap: () {
              Navigator.of(sheet).pop();
              onMoveEarlier?.call();
            },
          ),
          ListTile(
            key: const Key('move-later'),
            leading: const Icon(Icons.arrow_downward),
            title: const Text('Later in the rotation'),
            enabled: onMoveLater != null,
            onTap: () {
              Navigator.of(sheet).pop();
              onMoveLater?.call();
            },
          ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(AppRadius.md),
      child: InkWell(
        key: Key('zone-tile-$name'),
        borderRadius: BorderRadius.circular(AppRadius.md),
        onLongPress: () => unawaited(_sheet(context)),
        child: Row(
          children: [
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis),
            ),
            IconButton(
              key: Key('remove-$name'),
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.close),
              onPressed: onRemove,
            ),
          ],
        ),
      ),
    );
  }
}
