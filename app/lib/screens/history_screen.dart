import 'package:flutter/material.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/ui/theme.dart';

/// Every clean this phone has recorded, newest first.
///
/// Read-only by construction. There is deliberately no way to feed a stored
/// photo back into a new clean: camera-only capture is what makes a photo
/// evidence of cleaning *now*, and a "reuse this photo" affordance here
/// would quietly undo it.
class HistoryScreen extends StatelessWidget {
  /// Creates the screen.
  const HistoryScreen({required this.store, super.key});

  /// Durable session storage.
  final SessionStore store;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Past cleans')),
      body: FutureBuilder<List<CleanSession>>(
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
            itemBuilder: (context, i) => _Row(session: sessions[i]),
          );
        },
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.session});

  final CleanSession session;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = theme.extension<AppStatusColors>()!;
    final (icon, colour) = switch (session.status) {
      SessionStatus.accepted => (Icons.check_circle, status.success),
      SessionStatus.queued => (Icons.schedule, status.warning),
      SessionStatus.rejected => (Icons.info_outline, status.warning),
      SessionStatus.draft => (Icons.edit, theme.colorScheme.onSurfaceVariant),
    };
    final count = session.photoCount;
    return ListTile(
      key: Key('history-${session.id}'),
      contentPadding: EdgeInsets.zero,
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
