import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/models/clean_session.dart';
import 'package:home_guard_app/screens/history_screen.dart';
import 'package:home_guard_app/screens/home_body.dart';
import 'package:home_guard_app/screens/settings_screen.dart';
import 'package:home_guard_app/services/camera_capture.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';
import 'package:home_guard_app/services/session_store.dart';
import 'package:home_guard_app/services/upload_queue.dart';
import 'package:home_guard_app/services/zone_sync.dart';

/// Pick a place, photograph it as many times as it takes, finish.
///
/// The PC is no longer a precondition for any of that. Photos are written to
/// durable storage as they are taken, so nothing is lost if the upload fails
/// or never happens; the queue sends them when the PC is reachable.
class HomeScreen extends StatefulWidget {
  /// Creates the screen; every seam is injectable for tests.
  const HomeScreen({
    required this.deviceId,
    required this.store,
    super.key,
    this.sync,
    this.zoneSync,
    this.capture,
    this.encode,
    this.clock,
    this.confirmDelay = const Duration(seconds: 2),
  });

  /// This install's persisted device id, stamped on every upload.
  final String deviceId;

  /// Durable session storage.
  final SessionStore store;

  /// Firebase reads/writes; defaults to the real backend.
  final ChallengeSync? sync;

  /// The rotation; defaults to the real offline-first store.
  final ZoneSync? zoneSync;

  /// Camera capture; defaults to the in-app camera.
  final CaptureFn? capture;

  /// JPEG re-encoder; defaults to [encodePhotoUnderCap].
  final EncodedPhoto Function(Uint8List raw)? encode;

  /// Clock; defaults to [DateTime.now].
  final DateTime Function()? clock;

  /// Gap between asking the PC whether it took an upload. Zero in tests.
  final Duration confirmDelay;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final ChallengeSync _sync = widget.sync ?? ChallengeSync();
  late final ZoneSync _zones = widget.zoneSync ?? ZoneSync();
  late final CaptureFn _capture = widget.capture ?? captureFromCamera;
  late final EncodedPhoto Function(Uint8List) _encode =
      widget.encode ?? encodePhotoUnderCap;
  late final DateTime Function() _clock = widget.clock ?? DateTime.now;

  HomePhase _phase = HomePhase.loading;
  List<String> _zoneNames = [];
  String? _selected;
  String? _assigned;
  CleanSession? _session;
  String _detail = '';

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    _set(HomePhase.loading);
    final read = await _zones.load();
    if (!mounted) return;
    final names = read.zonesForDay(_zones.today());

    // Best effort, and only for decoration: the PC's suggestion pre-selects
    // a zone, but its absence never stops you cleaning something.
    final challenge = (await _sync.fetchChallenge()).challenge;
    if (!mounted) return;

    setState(() {
      _zoneNames = names;
      // Only while the slot is actually outstanding. Announcing "the PC is
      // waiting on desk" for a slot already cleared is a small lie the user
      // would act on.
      _assigned = (challenge != null && challenge.isSatisfiable(_clock()))
          ? challenge.zone
          : null;
      _selected ??= names.contains(challenge?.zone)
          ? challenge!.zone
          : names.firstOrNull;
      _phase = HomePhase.ready;
      _detail = switch (read.source) {
        ZoneSource.synced => '',
        ZoneSource.cached => 'Offline — using the last rotation the PC sent.',
        ZoneSource.fallback => 'Offline — using the default rotation.',
      };
    });
    unawaited(_drain());
    // Free old images only once storage is actually tight. Age-based pruning
    // would silently break browsing your own history a month in, which is
    // the whole reason the detail screen exists.
    unawaited(widget.store.prune(budgetBytes: kPhotoStorageBudgetBytes));
  }

  Future<void> _takePhoto() async {
    final zone = _selected;
    if (zone == null) return;
    _set(HomePhase.capturing);
    final raw = await _capture();
    if (!mounted) return;
    if (raw == null) {
      _set(HomePhase.ready, detail: 'No photo taken.');
      return;
    }
    try {
      // Re-encoded now so an over-cap shot is caught while the camera is
      // still in the user's hand, not at upload time hours later.
      _encode(raw);
    } on Object catch (e) {
      _set(HomePhase.ready, detail: 'Could not use that photo: $e');
      return;
    }
    final session = _session ?? _newSession(zone);
    final updated = await widget.store.addPhoto(session, raw);
    if (!mounted) return;
    setState(() {
      _session = updated;
      _phase = HomePhase.ready;
      _detail = '';
    });
  }

  CleanSession _newSession(String zone) {
    final now = _clock();
    return CleanSession(
      id: '${now.toUtc().millisecondsSinceEpoch}',
      zone: zone,
      capturedAt: now.toUtc().toIso8601String(),
      day: Challenge.dayOf(now),
      photos: const [],
      status: SessionStatus.draft,
    );
  }

  Future<void> _finish() async {
    final session = _session;
    if (session == null) return;
    _set(HomePhase.uploading);
    await widget.store.put(session.copyWith(status: SessionStatus.queued));
    final report = await _drain();
    if (!mounted) return;
    setState(() {
      _session = null;
      if (report.uploaded > 0) {
        _phase = HomePhase.accepted;
        _detail =
            'The PC recorded ${session.photoCount} photo'
            '${session.photoCount == 1 ? '' : 's'} of ${session.zone}.';
      } else {
        _phase = HomePhase.savedOffline;
        _detail = 'Saved here. It will reach the PC next time both are on.';
      }
    });
  }

  Future<DrainReport> _drain() async {
    final queue = UploadQueue(
      store: widget.store,
      sync: _sync,
      deviceId: widget.deviceId,
      clock: _clock,
      encode: _encode,
      confirmDelay: widget.confirmDelay,
    );
    return await queue.drain();
  }

  void _set(HomePhase phase, {String detail = ''}) {
    if (!mounted) return;
    setState(() {
      _phase = phase;
      _detail = detail;
    });
  }

  Future<void> _openSettings() async {
    await Navigator.of(
      context,
    ).push<void>(MaterialPageRoute(builder: (_) => const SettingsScreen()));
    await _refresh();
  }

  Future<void> _openHistory() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(builder: (_) => HistoryScreen(store: widget.store)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('home-guard'),
        actions: [
          IconButton(
            key: const Key('refresh'),
            tooltip: 'Check the PC again',
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
          IconButton(
            tooltip: 'Settings',
            icon: const Icon(Icons.settings),
            onPressed: _openSettings,
          ),
        ],
      ),
      body: HomeBody(
        phase: _phase,
        zones: _zoneNames,
        selectedZone: _selected,
        photoCount: _session?.photoCount ?? 0,
        detail: _detail,
        assignedZone: _assigned,
        onZoneSelected: (z) => setState(() => _selected = z),
        onTakePhoto: _takePhoto,
        onFinish: _finish,
        onOpenSettings: _openSettings,
        onOpenHistory: _openHistory,
      ),
    );
  }
}
