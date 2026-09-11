/// In-app, camera-only photo capture.
///
/// There is deliberately no gallery path anywhere in this app. The token
/// defeats replaying an old *upload*; only camera-only capture defeats
/// attaching a days-old photo of an already-clean room to today's echo.
/// Neither half is sufficient alone -- see `docs/DOCS-marker-protocol.md`.
library;

import 'dart:typed_data';

import 'package:image_picker/image_picker.dart';

/// Signature of a capture function: raw image bytes, or null if the user
/// backed out of the camera.
typedef CaptureFn = Future<Uint8List?> Function();

// The plugin reaches the camera through a platform channel `flutter test`
// has no binding for; the screen takes a [CaptureFn] so tests inject bytes.
// coverage:ignore-start

/// Opens the system camera and returns the shot, or null when cancelled.
///
/// `ImageSource.camera` is the only source this app ever passes. The
/// plugin's own `imageQuality`/`maxWidth` are left at defaults on purpose:
/// the size guarantee lives in `photo_encoder.dart`, where it is tested.
Future<Uint8List?> captureFromCamera() async {
  final shot = await ImagePicker().pickImage(
    source: ImageSource.camera,
    requestFullMetadata: false,
  );
  if (shot == null) return null;
  return await shot.readAsBytes();
}

// coverage:ignore-end
