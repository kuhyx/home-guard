import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:home_guard_app/services/photo_encoder.dart';
import 'package:image/image.dart' as img;

/// A noisy image: noise compresses badly, so the size cap actually bites.
Uint8List _noisy(int w, int h, {int seed = 7}) {
  final im = img.Image(width: w, height: h);
  var x = seed;
  for (final p in im) {
    x = (x * 1103515245 + 12345) & 0x7fffffff;
    p
      ..r = x & 0xff
      ..g = (x >> 8) & 0xff
      ..b = (x >> 16) & 0xff;
  }
  return Uint8List.fromList(img.encodePng(im));
}

void main() {
  test('cap matches the PC literal', () {
    expect(kMaxPhotoBytes, 600000);
  });

  test('a small photo passes through as JPEG under the cap', () {
    final out = encodePhotoUnderCap(_noisy(64, 48));
    expect(out.bytes.length, lessThan(kMaxPhotoBytes));
    expect(img.decodeJpg(out.bytes), isNotNull);
    expect(base64Decode(out.base64), out.bytes);
    expect(out.base64, isNot(contains('\n')));
    expect(out.base64, isNot(startsWith('data:')));
  });

  test('a large photo is downscaled to the max edge and fits the cap', () {
    // 3000x2000 of noise is several MB as PNG and well over the cap as a
    // quality-85 JPEG at full size -- the downscale is what has to bite.
    final out = encodePhotoUnderCap(_noisy(3000, 2000));
    expect(out.bytes.length, lessThan(kMaxPhotoBytes));
    final decoded = img.decodeJpg(out.bytes)!;
    expect(decoded.width, kMaxPhotoEdge);
    expect(decoded.height, lessThanOrEqualTo(kMaxPhotoEdge));
  });

  test('a portrait photo is scaled by its height', () {
    final out = encodePhotoUnderCap(_noisy(1000, 2600));
    final decoded = img.decodeJpg(out.bytes)!;
    expect(decoded.height, kMaxPhotoEdge);
    expect(decoded.width, lessThan(kMaxPhotoEdge));
  });

  test('undecodable bytes are a FormatException, not a crash', () {
    expect(
      () => encodePhotoUnderCap(Uint8List.fromList([1, 2, 3])),
      throwsFormatException,
    );
  });

  test('gives up loudly when no quality fits the cap', () {
    expect(
      () => encodePhotoUnderCap(_noisy(64, 48), maxBytes: 10),
      throwsA(isA<PhotoTooLargeError>()),
    );
  });

  test('PhotoTooLargeError names the smallest size reached', () {
    expect(
      PhotoTooLargeError(700000).toString(),
      contains('700000 bytes, cap is 600000'),
    );
  });
}
