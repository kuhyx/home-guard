/// The only file in the app that touches `dart:io` and `path_provider`.
///
/// Narrow on purpose: `SessionStore` holds all the logic and is 100% tested
/// against an in-memory fake, while the real adapter below has no test
/// binding available and is coverage-ignored, exactly as `camera_capture`
/// and `firebase_backend` already are.
library;

import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

/// Storage for session manifests and photo bytes.
abstract class SessionFiles {
  /// Reads the sessions index, or null when there is none yet.
  Future<String?> readIndex();

  /// Writes the sessions index.
  Future<void> writeIndex(String json);

  /// Stores photo bytes under [name].
  Future<void> writePhoto(String name, Uint8List bytes);

  /// Reads photo bytes, or null when the file is gone.
  Future<Uint8List?> readPhoto(String name);

  /// Deletes a photo; missing is not an error.
  Future<void> deletePhoto(String name);
}

// coverage:ignore-start
/// The real implementation, rooted at the app's documents directory.
class PathProviderSessionFiles implements SessionFiles {
  Directory? _root;

  Future<Directory> _dir() async {
    final cached = _root;
    if (cached != null) return cached;
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory('${base.path}/sessions');
    await dir.create(recursive: true);
    _root = dir;
    return dir;
  }

  File _indexFile(Directory dir) => File('${dir.path}/index.json');

  @override
  Future<String?> readIndex() async {
    final file = _indexFile(await _dir());
    if (!file.existsSync()) return null;
    return await file.readAsString();
  }

  @override
  Future<void> writeIndex(String json) async {
    await _indexFile(await _dir()).writeAsString(json);
  }

  @override
  Future<void> writePhoto(String name, Uint8List bytes) async {
    await File('${(await _dir()).path}/$name').writeAsBytes(bytes);
  }

  @override
  Future<Uint8List?> readPhoto(String name) async {
    final file = File('${(await _dir()).path}/$name');
    if (!file.existsSync()) return null;
    return await file.readAsBytes();
  }

  @override
  Future<void> deletePhoto(String name) async {
    final file = File('${(await _dir()).path}/$name');
    if (file.existsSync()) await file.delete();
  }
}
// coverage:ignore-end
