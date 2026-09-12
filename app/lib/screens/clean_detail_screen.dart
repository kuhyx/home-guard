import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/services/camera_capture.dart';
import 'package:home_guard_app/services/session_store.dart';

/// One past clean: its photos, and a way to add more.
///
/// Adding is **camera only**, exactly as on the home screen. Appending here
/// grants nothing -- the slot this clean satisfied is already settled -- so
/// it is purely you enriching your own record, and there is still no path
/// from a stored image back into a new clean.
class CleanDetailScreen extends StatefulWidget {
  /// Creates the screen.
  const CleanDetailScreen({
    required this.store,
    required this.session,
    super.key,
    this.capture,
  });

  /// Durable session storage.
  final SessionStore store;

  /// The clean being viewed.
  final CleanSession session;

  /// Camera capture; defaults to the in-app camera.
  final CaptureFn? capture;

  @override
  State<CleanDetailScreen> createState() => _CleanDetailScreenState();
}

class _CleanDetailScreenState extends State<CleanDetailScreen> {
  late final CaptureFn _capture = widget.capture ?? captureFromCamera;
  late CleanSession _session = widget.session;
  final Map<String, Uint8List?> _loaded = {};
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    unawaited(_loadPhotos());
  }

  Future<void> _loadPhotos() async {
    for (final photo in _session.photos) {
      final bytes = await widget.store.photo(photo.name);
      if (!mounted) return;
      setState(() => _loaded[photo.name] = bytes);
    }
  }

  Future<void> _addPhoto() async {
    setState(() => _busy = true);
    final raw = await _capture();
    if (!mounted) return;
    if (raw == null) {
      setState(() => _busy = false);
      return;
    }
    final updated = await widget.store.addPhoto(_session, raw);
    if (!mounted) return;
    setState(() {
      _session = updated;
      _loaded[updated.photos.last.name] = raw;
      _busy = false;
    });
  }

  void _open(String name) {
    final bytes = _loaded[name];
    if (bytes == null) return;
    Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: Text(_session.zone)),
          backgroundColor: Colors.black,
          body: Center(
            child: InteractiveViewer(
              child: Image.memory(bytes, key: const Key('full-photo')),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final count = _session.photoCount;
    return Scaffold(
      appBar: AppBar(title: Text(_session.zone)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                '${_session.day} · $count photo${count == 1 ? '' : 's'}',
                key: const Key('detail-subtitle'),
                style: theme.textTheme.bodyMedium,
              ),
            ),
          ),
          Expanded(child: _grid()),
          if (_busy) const LinearProgressIndicator(),
          Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton.icon(
              key: const Key('add-photo'),
              onPressed: _busy ? null : _addPhoto,
              // Camera, never a picker: see the class docstring.
              icon: const Icon(Icons.photo_camera),
              label: const Text('Take another photo'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _grid() {
    if (_session.photos.isEmpty) {
      return const Center(
        key: Key('detail-empty'),
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'The photos for this clean have been freed to save space. '
            'The record of it stays.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
      ),
      itemCount: _session.photos.length,
      itemBuilder: (context, i) {
        final name = _session.photos[i].name;
        final bytes = _loaded[name];
        return GestureDetector(
          key: Key('photo-$name'),
          onTap: () => _open(name),
          child: bytes == null
              ? ColoredBox(
                  color: Theme.of(context).colorScheme.surfaceContainerHigh,
                )
              : Image.memory(
                  bytes,
                  fit: BoxFit.cover,
                  // A single corrupt file must not take the whole grid down
                  // with it -- the rest of the clean is still viewable.
                  errorBuilder: (context, _, _) => ColoredBox(
                    color: Theme.of(context).colorScheme.surfaceContainerHigh,
                    child: const Icon(Icons.broken_image_outlined),
                  ),
                ),
        );
      },
    );
  }
}
