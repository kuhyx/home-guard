import 'dart:typed_data';

import 'package:home_guard_app/services/session_files.dart';

/// In-memory [SessionFiles]: an index string plus a name -> bytes map.
class FakeSessionFiles implements SessionFiles {
  /// The stored index, if any.
  String? index;

  /// Photo bytes by filename.
  final Map<String, Uint8List> photos = {};

  /// Every photo name ever deleted, so a test can assert pruning happened.
  final List<String> deleted = [];

  @override
  Future<String?> readIndex() async => index;

  @override
  Future<void> writeIndex(String json) async => index = json;

  @override
  Future<void> writePhoto(String name, Uint8List bytes) async =>
      photos[name] = bytes;

  @override
  Future<Uint8List?> readPhoto(String name) async => photos[name];

  @override
  Future<void> deletePhoto(String name) async {
    deleted.add(name);
    photos.remove(name);
  }
}
