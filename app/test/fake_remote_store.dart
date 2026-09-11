import 'package:crdt_sync/crdt_sync.dart';

/// An in-memory `RemoteStore`: a flat path -> text map.
class MemRemote implements RemoteStore {
  /// Files by logical path.
  final Map<String, String> files = {};

  /// Every path written, in order, so a test can assert "wrote nothing".
  final List<String> puts = [];

  @override
  Future<List<String>> listDirectory(String path) async {
    final prefix = '$path/';
    return files.keys
        .where((k) => k.startsWith(prefix))
        .map((k) => k.substring(prefix.length).split('/').first)
        .toSet()
        .toList();
  }

  @override
  Future<String?> getFileText(String path) async => files[path];

  @override
  Future<void> putFileText(
    String path,
    String text, {
    required String message,
  }) async {
    files[path] = text;
    puts.add(path);
  }

  @override
  Future<void> deleteFile(String path, {String? message}) async =>
      files.remove(path);

  @override
  Future<bool> canAccessRemote() async => true;

  @override
  void close() {}
}

/// A store whose every call fails, as an unreachable network would.
class BrokenRemote implements RemoteStore {
  @override
  Future<List<String>> listDirectory(String path) async =>
      throw RemoteSyncError('offline');

  @override
  Future<String?> getFileText(String path) async =>
      throw RemoteSyncError('offline');

  @override
  Future<void> putFileText(
    String path,
    String text, {
    required String message,
  }) async => throw RemoteSyncError('offline');

  @override
  Future<void> deleteFile(String path, {String? message}) async =>
      throw RemoteSyncError('offline');

  @override
  Future<bool> canAccessRemote() async => false;

  @override
  void close() {}
}
