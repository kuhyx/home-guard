import 'dart:async';

import 'package:flutter/material.dart';
import 'package:home_guard_app/models/zone_history.dart';
import 'package:home_guard_app/services/zone_sync.dart';

/// Edit the zone rotation from the phone.
///
/// Deliberately usable with no signal: [ZoneSync] reads the cache and writes
/// it before publishing, so adding "mirror" in a bathroom with no reception
/// works and is pushed later. The banner says which of those happened rather
/// than pretending everything is synced.
class ZonesScreen extends StatefulWidget {
  /// Creates the screen; [sync] is injectable for tests.
  const ZonesScreen({this.sync, super.key});

  /// The rotation store. Defaults to a real [ZoneSync].
  final ZoneSync? sync;

  @override
  State<ZonesScreen> createState() => _ZonesScreenState();
}

class _ZonesScreenState extends State<ZonesScreen> {
  late final ZoneSync _sync = widget.sync ?? ZoneSync();
  final _controller = TextEditingController();

  List<String> _zones = [];
  ZoneSource _source = ZoneSource.fallback;
  bool _loading = true;
  String _detail = '';

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final read = await _sync.load();
    if (!mounted) return;
    setState(() {
      _zones = List<String>.from(read.zonesForDay(_sync.today()));
      _source = read.source;
      _loading = false;
      _detail = switch (read.source) {
        ZoneSource.synced => 'Up to date with the PC.',
        ZoneSource.cached =>
          'Showing the last rotation seen; the PC is offline.',
        ZoneSource.fallback => 'No rotation yet — these are the defaults.',
      };
    });
  }

  Future<void> _save(List<String> zones) async {
    setState(() {
      _zones = zones;
      _detail = 'Saving…';
    });
    final published = await _sync.setZones(zones);
    if (!mounted) return;
    setState(() {
      _source = published ? ZoneSource.synced : ZoneSource.cached;
      _detail = published
          ? 'Saved and sent to the PC.'
          : 'Saved on this phone. It will reach the PC when you have signal.';
    });
  }

  void _add() {
    final name = _controller.text.trim();
    if (name.isEmpty || _zones.contains(name)) {
      _controller.clear();
      return;
    }
    _controller.clear();
    unawaited(_save([..._zones, name]));
  }

  void _removeAt(int index) {
    if (_zones.length == 1) {
      setState(() => _detail = 'A rotation needs at least one zone.');
      return;
    }
    final next = [..._zones]..removeAt(index);
    unawaited(_save(next));
  }

  void _reorder(int oldIndex, int newIndex) =>
      unawaited(_save(ZoneHistory.reorder(_zones, oldIndex, newIndex)));

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Zones')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: Row(
                    children: [
                      Icon(
                        _source == ZoneSource.synced
                            ? Icons.cloud_done
                            : Icons.cloud_off,
                        size: 18,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _detail,
                          key: const Key('zones-detail'),
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: ReorderableListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _zones.length,
                    onReorderItem: _reorder,
                    itemBuilder: (context, i) => ListTile(
                      key: ValueKey(_zones[i]),
                      title: Text(_zones[i]),
                      leading: const Icon(Icons.drag_handle),
                      trailing: IconButton(
                        key: Key('remove-${_zones[i]}'),
                        icon: const Icon(Icons.close),
                        onPressed: () => _removeAt(i),
                      ),
                    ),
                  ),
                ),
                Padding(
                  padding: EdgeInsets.fromLTRB(
                    16,
                    0,
                    16,
                    16 + MediaQuery.of(context).viewInsets.bottom,
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          key: const Key('zone-input'),
                          controller: _controller,
                          textCapitalization: TextCapitalization.sentences,
                          decoration: const InputDecoration(
                            labelText: 'Add a place you clean',
                            hintText: 'mirror',
                          ),
                          onSubmitted: (_) => _add(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      FilledButton(
                        key: const Key('zone-add'),
                        onPressed: _add,
                        child: const Text('Add'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
    );
  }
}
