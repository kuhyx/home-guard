/// Shrinks a captured photo until its decoded bytes fit the PC's cap.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:image/image.dart' as img;

/// Hard cap the PC enforces AFTER base64-decoding
/// (`home_guard/_constants.py::MAX_EVIDENCE_PHOTO_BYTES`). The phone's
/// number must never be looser than the PC's, so it is the same literal.
const int kMaxPhotoBytes = 600000;

/// Longest edge the photo is downscaled to before quality is reduced.
/// Accountability, not forensics: a 1280px shot shows whether a desk is
/// clear; it does not need to show the grain of the wood.
const int kMaxPhotoEdge = 1280;

/// The encoded photo ready to upload.
class EncodedPhoto {
  /// Creates an encoded photo.
  const EncodedPhoto({required this.bytes, required this.base64});

  /// JPEG bytes, guaranteed `< kMaxPhotoBytes`.
  final Uint8List bytes;

  /// Standard-alphabet base64 of [bytes] -- no line breaks, no `data:`
  /// prefix, because the PC decodes with `validate=True`.
  final String base64;
}

/// Thrown when no quality setting brings the photo under the cap.
///
/// Practically unreachable after the downscale (a 1280px JPEG at quality 30
/// is tens of kilobytes), but the guarantee must be a check, not a hope.
class PhotoTooLargeError extends Error {
  /// Creates the error with the smallest size reached.
  PhotoTooLargeError(this.smallestBytes);

  /// The smallest encoding attempted, in bytes.
  final int smallestBytes;

  @override
  String toString() =>
      'PhotoTooLargeError: smallest encoding was $smallestBytes bytes, '
      'cap is $kMaxPhotoBytes';
}

/// Decodes [raw] (any format `image` understands), downscales to
/// [kMaxPhotoEdge], and re-encodes as JPEG at descending quality until the
/// result is under [kMaxPhotoBytes].
///
/// Pure and synchronous so the size guarantee is unit-tested with a
/// generated image rather than trusted to the camera plugin's own
/// `imageQuality` knob, which documents no size bound at all. [maxBytes]
/// exists only so a test can force the give-up path; production always
/// uses the PC's cap.
EncodedPhoto encodePhotoUnderCap(
  Uint8List raw, {
  int maxBytes = kMaxPhotoBytes,
}) {
  final img.Image? decoded;
  try {
    decoded = img.decodeImage(raw);
  } on Object catch (e) {
    // `image` probes every decoder it has and some throw RangeError on
    // truncated input rather than returning null; the caller wants one
    // exception type for "not a photo".
    throw FormatException('not a decodable image: $e');
  }
  if (decoded == null) {
    throw const FormatException('not a decodable image');
  }
  var frame = decoded;
  if (frame.width > kMaxPhotoEdge || frame.height > kMaxPhotoEdge) {
    frame = frame.width >= frame.height
        ? img.copyResize(frame, width: kMaxPhotoEdge)
        : img.copyResize(frame, height: kMaxPhotoEdge);
  }
  var smallest = -1;
  for (final quality in const [85, 70, 55, 40, 30, 20]) {
    final bytes = Uint8List.fromList(img.encodeJpg(frame, quality: quality));
    if (bytes.length < maxBytes) {
      return EncodedPhoto(bytes: bytes, base64: base64Encode(bytes));
    }
    smallest = bytes.length; // qualities descend, so the last is smallest
  }
  throw PhotoTooLargeError(smallest);
}
