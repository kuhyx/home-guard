import 'dart:async';

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
      appBar: AppBar(title: const Text('Past cleans')),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('log-a-clean'),
        onPressed: () => unawaited(_open(LogCleanScreen(store: store))),
        icon: const Icon(Icons.add),
        label: const Text('Log a clean'),
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
              child: Text('Nothing recorded yet.'),
            );
          }
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: sessions.length,
            itemBuilder: (context, i) => _Row(
              session: sessions[i],
              onTap: () => unawaited(
                _open(CleanDetailScreen(store: store, session: sessions[i])),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.session, required this.onTap});

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
    return ListTile(
      key: Key('history-${session.id}'),
      contentPadding: EdgeInsets.zero,
      onTap: onTap,
      trailing: const Icon(Icons.chevron_right),
      leading: Icon(icon, color: colour),
      title: Text(session.zone),
      subtitle: Text(
        [
          session.day,
          if (count > 0) '$count photo${count == 1 ? '' : 's'}',
          if (session.detail.isNotEmpty) session.detail,
        ].join(' · '),
      ),
    );
  }
}
