import 'dart:async';

import 'package:design_system/design_system.dart'
    show AppRadius, AppSpacing, FitGrid;
import 'package:flutter/material.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/screens/clean_detail_screen.dart';
import 'package:home_guard_app/screens/log_clean_screen.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/ui/theme.dart';

/// Every clean this phone has recorded, newest first.
///
/// Tapping one opens its photos. There is deliberately no way to feed a
/// stored photo back into a new clean: camera-only capture is what makes a
/// photo evidence of cleaning *now*, and a "reuse this photo" affordance
/// anywhere in this app would quietly undo it. Adding photos, here or on the
/// detail screen, always opens the camera.
class HistoryScreen extends StatefulWidget {
  /// Creates the screen.
  const HistoryScreen({required this.store, super.key});

  /// Durable session storage.
  final SessionStore store;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  int _reload = 0;

  Future<void> _open(Widget screen) async {
    await Navigator.of(
      context,
    ).push<void>(MaterialPageRoute(builder: (_) => screen));
    // Photos may have been added while we were away.
    if (mounted) setState(() => _reload++);
  }

  @override
  Widget build(BuildContext context) {
    final store = widget.store;
    return Scaffold(
      key: const Key('history-screen'),
      appBar: AppBar(
        title: const Icon(Icons.history, semanticLabel: 'Past cleans'),
      ),
      floatingActionButton: FloatingActionButton(
        key: const Key('log-a-clean'),
        onPressed: () => unawaited(_open(LogCleanScreen(store: store))),
        child: const Icon(Icons.add, semanticLabel: 'Log a clean'),
      ),
      body: FutureBuilder<List<CleanSession>>(
        key: ValueKey(_reload),
        future: store.load(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final sessions = snapshot.data!;
          if (sessions.isEmpty) {
            return const Center(
              key: Key('history-empty'),
              child: Icon(
                Icons.inbox_outlined,
                size: 64,
                semanticLabel: 'Nothing recorded yet.',
              ),
            );
          }
          // Bottom gap keeps the last row clear of the floating button.
          return Padding(
            padding: const EdgeInsets.only(bottom: 80),
            child: FitGrid(
              minSquare: 0.8,
              padding: const EdgeInsets.all(16),
              itemCount: sessions.length,
              itemBuilder: (context, i) => _Tile(
                session: sessions[i],
                onTap: () => unawaited(
                  _open(CleanDetailScreen(store: store, session: sessions[i])),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.session, required this.onTap});

  final CleanSession session;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = theme.extension<AppStatusColors>()!;
    final (icon, colour) = switch (session.status) {
      SessionStatus.accepted => (Icons.check_circle, status.success),
      SessionStatus.queued => (Icons.schedule, status.warning),
      SessionStatus.rejected => (Icons.info_outline, status.warning),
      SessionStatus.draft => (Icons.edit, theme.colorScheme.onSurfaceVariant),
      SessionStatus.selfLogged => (
        Icons.bookmark_added_outlined,
        theme.colorScheme.onSurfaceVariant,
      ),
    };
    final count = session.photoCount;
    return Material(
      color: theme.colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(AppRadius.md),
      child: InkWell(
        key: Key('history-${session.id}'),
        borderRadius: BorderRadius.circular(AppRadius.md),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.sm),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: colour),
              Text(
                session.zone,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
              ),
              Semantics(
                label: [
                  session.day,
                  if (count > 0) '$count photo${count == 1 ? '' : 's'}',
                ].join(' · '),
                excludeSemantics: true,
                child: Wrap(
                  key: Key('history-meta-${session.id}'),
                  alignment: WrapAlignment.center,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 4,
                  children: [
                    Text(
                      session.day.replaceFirst(RegExp(r'^\d{4}-'), ''),
                      style: theme.textTheme.bodySmall,
                    ),
                    if (count > 0) ...[
                      const Icon(Icons.photo_camera, size: 14),
                      Text('$count', style: theme.textTheme.bodySmall),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
