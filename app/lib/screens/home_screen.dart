import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:home_guard_app/models/challenge.dart';
import 'package:home_guard_app/screens/home_body.dart';
import 'package:home_guard_app/screens/settings_screen.dart';
import 'package:home_guard_app/services/camera_capture.dart';
import 'package:home_guard_app/services/challenge_sync.dart';
import 'package:home_guard_app/services/photo_encoder.dart';

/// The one screen: which zone the PC is waiting on, and the camera button.
class HomeScreen extends StatefulWidget {
  /// Creates the screen; every seam is injectable for tests.
  const HomeScreen({
    required this.deviceId,
    super.key,
    this.sync,
    this.capture,
    this.encode,
    this.clock,
    this.pollInterval = const Duration(seconds: 3),
    this.pollAttempts = 20,
  });

  /// This install's persisted device id, stamped on every upload.
  final String deviceId;

  /// Firebase reads/writes; defaults to the real backend.
  final ChallengeSync? sync;

  /// Camera capture; defaults to the in-app camera.
  final CaptureFn? capture;

  /// JPEG re-encoder; defaults to [encodePhotoUnderCap].
  final EncodedPhoto Function(Uint8List raw)? encode;

  /// Clock for the day check; defaults to [DateTime.now].
  final DateTime Function()? clock;

  /// How often to ask whether the PC has drained the evidence.
  final Duration pollInterval;

  /// How many polls before giving up on an "accepted" signal.
  final int pollAttempts;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final ChallengeSync _sync = widget.sync ?? ChallengeSync();
  late final CaptureFn _capture = widget.capture ?? captureFromCamera;
  late final EncodedPhoto Function(Uint8List) _encode =
      widget.encode ?? encodePhotoUnderCap;
  late final DateTime Function() _clock = widget.clock ?? DateTime.now;

  HomePhase _phase = HomePhase.loading;
  Challenge? _challenge;
  String _detail = '';

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    _set(HomePhase.loading);
    final read = await _sync.fetchChallenge();
    if (!mounted) return;
    switch (read.outcome) {
      case SyncOutcome.notConfigured:
        _set(HomePhase.notConfigured, detail: read.detail);
      case SyncOutcome.error:
        _set(HomePhase.error, detail: read.detail);
      case SyncOutcome.noChallenge:
        _set(HomePhase.noChallenge, detail: read.detail);
      case SyncOutcome.ok:
        final c = read.challenge!;
        _challenge = c;
        if (c.consumed) {
          _set(HomePhase.consumed, detail: 'Already cleared for ${c.day}.');
        } else if (!c.isSatisfiable(_clock())) {
          _set(
            HomePhase.stale,
            detail:
                'The PC last published a challenge for ${c.day}; '
                'it will mint a new one when a slot is next due.',
          );
        } else {
          _set(HomePhase.ready);
        }
    }
  }

  Future<void> _takePhoto() async {
    final challenge = _challenge;
    if (challenge == null) return;
    _set(HomePhase.capturing);
    final raw = await _capture();
    if (!mounted) return;
    if (raw == null) {
      _set(HomePhase.ready, detail: 'No photo taken.');
      return;
    }
    _set(HomePhase.uploading);
    final EncodedPhoto photo;
    try {
      photo = _encode(raw);
    } on Object catch (e) {
      _set(HomePhase.ready, detail: 'Could not encode the photo: $e');
      return;
    }
    final result = await _sync.uploadEvidence(
      challenge: challenge,
      photo: photo,
      deviceId: widget.deviceId,
    );
    if (!mounted) return;
    if (result.outcome != SyncOutcome.ok) {
      _set(HomePhase.ready, detail: result.detail);
      return;
    }
    await _awaitAcceptance();
  }

  /// Polls until the PC drains the evidence node (its "accepted" signal).
  Future<void> _awaitAcceptance() async {
    _set(HomePhase.awaitingPc);
    for (var i = 0; i < widget.pollAttempts; i++) {
      await Future<void>.delayed(widget.pollInterval);
      if (!mounted) return;
      final drained = await _sync.evidenceDrained();
      if (!mounted) return;
      if (drained ?? false) {
        _set(HomePhase.accepted, detail: 'The PC accepted the photo.');
        return;
      }
    }
    _set(
      HomePhase.unconfirmed,
      detail:
          'Uploaded, but the PC has not accepted it yet. If the lock '
          'is showing, give it a moment; otherwise it is not running the '
          'gate right now and will pick this up when it next is.',
    );
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
    // Connecting Firebase in Settings changes the answer to every fetch.
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('home-guard'),
        actions: [
          IconButton(
            tooltip: 'Settings',
            icon: const Icon(Icons.settings),
            onPressed: _openSettings,
          ),
        ],
      ),
      body: HomeBody(
        phase: _phase,
        challenge: _challenge,
        detail: _detail,
        onTakePhoto: _takePhoto,
        onRefresh: _refresh,
        onOpenSettings: _openSettings,
      ),
    );
  }
}
