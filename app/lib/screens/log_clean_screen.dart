import 'dart:async';

import 'package:flutter/material.dart';
import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/services/camera_capture.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/services/zone_sync.dart';

/// Record a clean the app never saw: pick a zone, pick the day, photograph it.
///
/// Saved as [SessionStatus.selfLogged] and never uploaded. A backdated clean
/// cannot be credited without spending today's single-use token on work that
/// belongs in a past log bucket, which would leave today both uncredited and
/// unclearable -- so this is honestly a record for you, not a claim on the
/// gate. Photos are camera-only here as everywhere else.
class LogCleanScreen extends StatefulWidget {
  /// Creates the screen.
  const LogCleanScreen({
    required this.store,
    super.key,
    this.zoneSync,
    this.capture,
    this.clock,
  });

  /// Durable session storage.
  final SessionStore store;

  /// The rotation; defaults to the real offline-first store.
  final ZoneSync? zoneSync;

  /// Camera capture; defaults to the in-app camera.
  final CaptureFn? capture;

  /// Clock; defaults to [DateTime.now].
  final DateTime Function()? clock;

  @override
  State<LogCleanScreen> createState() => _LogCleanScreenState();
}

class _LogCleanScreenState extends State<LogCleanScreen> {
  late final ZoneSync _zones = widget.zoneSync ?? ZoneSync();
  late final CaptureFn _capture = widget.capture ?? captureFromCamera;
  late final DateTime Function() _clock = widget.clock ?? DateTime.now;

  List<String> _zoneNames = [];
  String? _zone;
  late DateTime _day = _clock();
  CleanSession? _session;
  bool _busy = true;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    final read = await _zones.load();
    if (!mounted) return;
    setState(() {
      _zoneNames = read.zonesForDay(_zones.today());
      _zone ??= _zoneNames.firstOrNull;
      _busy = false;
    });
  }

  Future<void> _pickDay() async {
    final now = _clock();
    final picked = await showDatePicker(
      context: context,
      initialDate: _day,
      // Forward-only in the other direction: you cannot log a clean you have
      // not done yet.
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now,
    );
    if (picked != null && mounted) setState(() => _day = picked);
  }

  Future<void> _addPhoto() async {
    final zone = _zone;
    if (zone == null) return;
    setState(() => _busy = true);
    final raw = await _capture();
    if (!mounted) return;
    if (raw == null) {
      setState(() => _busy = false);
      return;
    }
    final session = _session ?? _newSession(zone);
    final updated = await widget.store.addPhoto(session, raw);
    if (!mounted) return;
    setState(() {
      _session = updated;
      _busy = false;
    });
  }

  CleanSession _newSession(String zone) => CleanSession(
    id: 'self-${_clock().toUtc().millisecondsSinceEpoch}',
    zone: zone,
    capturedAt: _day.toUtc().toIso8601String(),
    day: Challenge.dayOf(_day),
    photos: const [],
    status: SessionStatus.selfLogged,
  );

  Future<void> _save() async {
    final session = _session;
    if (session == null) return;
    await widget.store.put(session.copyWith(status: SessionStatus.selfLogged));
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final count = _session?.photoCount ?? 0;
    return Scaffold(
      appBar: AppBar(title: const Text('Log a clean')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ListTile(
              key: const Key('pick-day'),
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.event),
              title: Text(Challenge.dayOf(_day)),
              subtitle: const Text('When you cleaned it'),
              trailing: const Icon(Icons.edit),
              onTap: _pickDay,
            ),
            const SizedBox(height: 8),
            Expanded(
              child: SingleChildScrollView(
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final zone in _zoneNames)
                      ChoiceChip(
                        key: Key('log-zone-$zone'),
                        label: Text(zone),
                        selected: zone == _zone,
                        onSelected: count > 0
                            ? null
                            : (_) => setState(() => _zone = zone),
                      ),
                  ],
                ),
              ),
            ),
            Text(
              count == 0
                  ? 'Take at least one photo.'
                  : '$count photo${count == 1 ? '' : 's'}. Stays on the '
                        'phone — a record, not a claim on the gate.',
              key: const Key('log-detail'),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            if (_busy) const LinearProgressIndicator(),
            FilledButton.icon(
              key: const Key('log-add-photo'),
              onPressed: _busy || _zone == null ? null : _addPhoto,
              icon: const Icon(Icons.photo_camera),
              label: Text(count == 0 ? 'Take a photo' : 'Another photo'),
            ),
            const SizedBox(height: 8),
            OutlinedButton(
              key: const Key('log-save'),
              onPressed: count == 0 || _busy ? null : _save,
              child: const Text('Save this clean'),
            ),
          ],
        ),
      ),
    );
  }
}
