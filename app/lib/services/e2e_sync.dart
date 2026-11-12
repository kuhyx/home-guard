/// End-to-end encryption of every home-guard RTDB payload.
///
/// Every client the app syncs through is crdt_sync's encrypting store: the
/// challenge, evidence and zone nodes live under `home-guard-sync-e2e` and
/// are sealed with a key derived (Argon2id) from the shared crdt-sync
/// passphrase in the OS keystore. With no passphrase, or the wrong one,
/// there is no client at all, so nothing can ever be written in plaintext;
/// [e2eLocked] tells the UI to show the lock button.
///
/// Mirrors `home_guard/_sync_client.py`, which derives the same paths.
library;

import 'package:crdt_sync/crdt_sync.dart';
import 'package:crdt_sync_flutter/crdt_sync_flutter.dart';
import 'package:flutter/foundation.dart';
import 'package:home_guard_app/services/firebase_backend.dart';

/// The pre-E2E prefix. Never written, never deleted by this app.
const kOldSyncPrefix = 'home-guard-sync';

/// `E2eLayout.of(kOldSyncPrefix).prefix`, spelled out so paths stay const.
const kSyncPrefix = 'home-guard-sync-e2e';

/// Whether the last open found no usable key (missing or wrong passphrase).
final ValueNotifier<bool> e2eLocked = ValueNotifier<bool>(false);

/// Opens the signed-in Firebase client wrapped in the encrypting store.
///
/// Null when sync is not configured or when it is locked; never throws
/// past what [openClient] throws.
Future<RemoteStore?> openEncryptedFirebase({
  Future<RemoteStore?> Function()? openClient,
  Argon2Params params = Argon2Params.recommended,
}) async {
  final client = await (openClient ?? openFirebase)();
  if (client == null) {
    e2eLocked.value = false;
    return null;
  }
  final state = await openEncryptedStoreFromKeystore(
    store: _NoLegacyCopy(client),
    oldPrefix: kOldSyncPrefix,
    params: params,
  );
  if (state is E2eReady) {
    e2eLocked.value = false;
    return state.store;
  }
  // Fail closed: no client means no pull and no push this round.
  e2eLocked.value = true;
  return null;
}

/// Delegates to the inner store but lists nothing under the old prefix.
///
/// The library's one-time copy merges the old prefix's CRDT logs into the
/// new one. home-guard has none: its nodes are plain JSON transport blobs,
/// so the only thing the copy could ever pick up is the drained `{}`
/// evidence node (it parses as an empty log), and merging that onto a
/// pending upload would wipe the photos and fake the PC's "accepted" signal.
/// Hiding the old prefix makes the copy a no-op; the old data stays put.
class _NoLegacyCopy implements RemoteStore {
  _NoLegacyCopy(this._inner);

  final RemoteStore _inner;

  @override
  Future<List<String>> listDirectory(String path) => path == kOldSyncPrefix
      ? Future.value(const <String>[])
      : _inner.listDirectory(path);

  @override
  Future<String?> getFileText(String path) => _inner.getFileText(path);

  @override
  Future<void> putFileText(
    String path,
    String text, {
    required String message,
  }) => _inner.putFileText(path, text, message: message);

  @override
  Future<void> deleteFile(String path, {String message = ''}) =>
      _inner.deleteFile(path, message: message);

  @override
  Future<bool> canAccessRemote() => _inner.canAccessRemote();

  @override
  void close() => _inner.close();
}
