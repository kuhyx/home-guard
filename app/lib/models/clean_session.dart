/// One clean: a zone, and however many photos it took.
library;

/// Where a session is in its life.
enum SessionStatus {
  /// Being photographed right now.
  draft,

  /// Finished, waiting to reach the PC.
  queued,

  /// The PC took it.
  accepted,

  /// The PC refused it. Kept, not dropped, so it stays visible in history
  /// rather than silently vanishing along with the work it records.
  rejected,
}

/// A clean, stored on the phone first and uploaded second.
///
/// The phone is the durable store: photo bytes used to live only in a local
/// variable between capture and upload, so any failure lost the shot. A
/// session owns its files and survives the app being closed.
class CleanSession {
  /// Creates a session.
  const CleanSession({
    required this.id,
    required this.zone,
    required this.capturedAt,
    required this.day,
    required this.photoNames,
    required this.status,
    this.slot,
    this.token,
    this.detail = '',
  });

  /// Parses a stored manifest; null if it is not one.
  static CleanSession? fromJson(Object? json) {
    if (json is! Map<String, Object?>) return null;
    final id = json['id'];
    final zone = json['zone'];
    final capturedAt = json['captured_at'];
    final day = json['day'];
    final photos = json['photos'];
    final status = json['status'];
    if (id is! String ||
        zone is! String ||
        capturedAt is! String ||
        day is! String ||
        photos is! List ||
        status is! String) {
      return null;
    }
    final slot = json['slot'];
    final token = json['token'];
    final detail = json['detail'];
    return CleanSession(
      id: id,
      zone: zone,
      capturedAt: capturedAt,
      day: day,
      photoNames: photos.whereType<String>().toList(),
      status: SessionStatus.values.firstWhere(
        (s) => s.name == status,
        orElse: () => SessionStatus.queued,
      ),
      slot: slot is String ? slot : null,
      token: token is String ? token : null,
      detail: detail is String ? detail : '',
    );
  }

  /// Stable id, also the photo filename prefix.
  final String id;

  /// The zone cleaned. Must be in the rotation for the PC to accept it.
  final String zone;

  /// ISO-8601 UTC instant the session was started.
  final String capturedAt;

  /// Local `YYYY-MM-DD` the cleaning happened, the way the PC formats a day.
  ///
  /// Sent alongside [capturedAt] so the PC credits the day you cleaned, not
  /// the day it happened to drain the node.
  final String day;

  /// Photo filenames, in capture order. Unbounded on purpose.
  final List<String> photoNames;

  /// Where it is in its life.
  final SessionStatus status;

  /// The slot this was for, when a challenge was available.
  final String? slot;

  /// The PC's single-use token, when one was available. Null for a session
  /// captured with no challenge published -- the PC decides what to do with
  /// that on arrival.
  final String? token;

  /// Why it was rejected, when it was.
  final String detail;

  /// How many photos this clean took.
  int get photoCount => photoNames.length;

  /// Serialises the manifest.
  Map<String, Object?> toJson() => {
    'id': id,
    'zone': zone,
    'captured_at': capturedAt,
    'day': day,
    'photos': photoNames,
    'status': status.name,
    if (slot != null) 'slot': slot,
    if (token != null) 'token': token,
    if (detail.isNotEmpty) 'detail': detail,
  };

  /// Returns a copy with the given fields replaced.
  CleanSession copyWith({
    List<String>? photoNames,
    SessionStatus? status,
    String? slot,
    String? token,
    String? detail,
  }) => CleanSession(
    id: id,
    zone: zone,
    capturedAt: capturedAt,
    day: day,
    photoNames: photoNames ?? this.photoNames,
    status: status ?? this.status,
    slot: slot ?? this.slot,
    token: token ?? this.token,
    detail: detail ?? this.detail,
  );
}
