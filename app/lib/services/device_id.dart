/// This install's persisted sync device id.
library;

import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// SharedPreferences key holding this install's device id.
///
/// The same key every sibling app (`todo`, `diet_guard_app`, `wake_alarm`)
/// uses for the same purpose.
const kDeviceIdKey = 'crdt.nodeId';

/// Loads (or mints and persists) this install's device id.
///
/// A per-install uuid rather than a fixed `phone` constant: the PC logs the
/// id with every accepted clear, and two phones sharing one would be
/// indistinguishable in that history. Idempotent.
Future<String> initDeviceId({SharedPreferences? prefs}) async {
  final store = prefs ?? await SharedPreferences.getInstance();
  final existing = store.getString(kDeviceIdKey);
  if (existing != null && existing.isNotEmpty) return existing;
  final minted = const Uuid().v4();
  await store.setString(kDeviceIdKey, minted);
  return minted;
}
