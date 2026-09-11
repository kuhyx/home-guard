/// The PC's published challenge: which zone is due, under which token.
library;

/// One `(day, slot)` challenge as the PC publishes it to
/// `home-guard-sync/challenge/current.json`.
///
/// Every field is carried **verbatim** back in the evidence upload. The PC
/// compares `token` and `zone` by exact string equality against its own
/// local record (`home_guard/_challenge.py::verify_evidence`), so nothing
/// here may be normalised, trimmed or recomputed on the phone.
class Challenge {
  /// Creates a challenge; see [Challenge.fromJson] for the wire shape.
  const Challenge({
    required this.day,
    required this.slot,
    required this.zone,
    required this.token,
    required this.issuedAt,
    required this.consumed,
  });

  /// Parses the PC's JSON. Returns null when any field is missing or of
  /// the wrong type -- a half-written or foreign payload must read as "no
  /// challenge", never as a challenge with blank fields the PC would reject.
  static Challenge? fromJson(Object? json) {
    if (json is! Map<String, Object?>) return null;
    final day = json['day'];
    final slot = json['slot'];
    final zone = json['zone'];
    final token = json['token'];
    final issuedAt = json['issued_at'];
    final consumed = json['consumed'];
    if (day is! String ||
        slot is! String ||
        zone is! String ||
        token is! String ||
        issuedAt is! String ||
        consumed is! bool) {
      return null;
    }
    if (day.isEmpty || slot.isEmpty || zone.isEmpty || token.isEmpty) {
      return null;
    }
    return Challenge(
      day: day,
      slot: slot,
      zone: zone,
      token: token,
      issuedAt: issuedAt,
      consumed: consumed,
    );
  }

  /// Local calendar day, `YYYY-MM-DD`.
  final String day;

  /// Slot key, `HHMM` (e.g. `0800`).
  final String slot;

  /// The zone the PC is waiting on, verbatim.
  final String zone;

  /// The single-use token to echo back.
  final String token;

  /// When the PC minted it (ISO-8601, informational only).
  final String issuedAt;

  /// True once the PC has already accepted a photo for this slot.
  final bool consumed;

  /// Formats [now] the way the PC formats `day` (`strftime("%Y-%m-%d")`,
  /// local time).
  static String dayOf(DateTime now) {
    final local = now.toLocal();
    final m = local.month.toString().padLeft(2, '0');
    final d = local.day.toString().padLeft(2, '0');
    return '${local.year}-$m-$d';
  }

  /// Whether uploading a photo for this challenge could possibly be
  /// accepted right now.
  ///
  /// A consumed challenge, or one minted for a different day than the PC
  /// would look it up under, is a guaranteed reject -- the screen says so
  /// instead of uploading.
  bool isSatisfiable(DateTime now) => !consumed && day == dayOf(now);
}
