# The anti-replay marker protocol

## The problem

Every sibling gate's evidence is externally sourced and hard to fake: a
RunnerUp TCX file pulled via ADB, a LeetCode submission id from the public
API, two distinct NFC tag ids in different rooms. "My home is clear" has no
such oracle — there is no third-party service that can attest a photo shows
a genuinely tidied zone, and this repo's owner has a hard rule that an LLM
must never sit in that pass/fail adjudication loop (grading a photo's
tidiness would be exactly that).

So home-guard doesn't try to verify tidiness at all. A photo is required for
every clear, but purely for accountability — stored, browsable later, never
graded. What actually needs verifying is much narrower: that the phone
attested to *this specific, single-use challenge*, not a replay of an old
upload.

## Two designs considered

**Provisioning a shared secret to the phone** (a one-time pairing, QR-scan-once
like wake-alarm's NFC tag registration) was the first idea: both sides derive
an HMAC-based token from a secret only they share, no network round trip
needed to check it. Rejected — it buys nothing over a plain echo. The threat
model here is the user's own self-discipline, not a third party; a user
willing to defeat camera-only capture (see below) could equally compute an
HMAC over an arbitrary photo. The pairing step is real UX cost for a
protection that doesn't protect against the actual adversary.

**Publish-then-echo** (adopted): the PC mints a random token, publishes it,
and only accepts a photo whose upload echoes that exact token back. No
secret ever reaches the phone.

## The protocol

1. PC mints `token = secrets.token_urlsafe(24)` for `(day, slot)`, and a
   `ChallengeRecord(day, slot, zone, token, issued_at, consumed=False)`.
2. Persisted **locally first** (`_challenge_store.py`,
   `~/.local/share/home_guard/challenges.json`, atomic write, HMAC-signed
   with the shared `/etc/workout-locker/hmac.key`). This file is the sole
   authority; RTDB only ever carries a copy in transit. One record per
   `(day, slot)`, minted once — a failed attempt doesn't get a second chance
   at the same slot with a stale photo.
3. **Published** to `home-guard-sync/challenge/current.json`:
   `{day, slot, zone, token, issued_at}`.
4. Phone fetches that path, shows the zone, and — after an **in-app
   camera-only** photo (no gallery picker; see below) — uploads to
   `home-guard-sync/evidence/current.json`:
   `{day, slot, zone, token (echoed verbatim), device_id, captured_at,
   photo_b64, photo_mime}`.
5. PC's `EvidencePoller` fetches that path off the Tk thread.
6. **Accept/reject** (`_challenge.py: verify_evidence`, pure and
   deterministic): reject if no matching local record, already consumed,
   token mismatch, or zone mismatch (checked against the zone *as recorded
   in the challenge*, not a freshly-read current zone, so a rotation change
   mid-flight can't be exploited either direction). On accept: mark
   consumed, write the `clear:<day>:<slot>` log entry, advance the zone
   cursor, drain the RTDB evidence node.

## Why camera-only capture matters as much as the token

The token defeats replaying an *old upload*. It does nothing against
uploading a *fresh photo of an already-clean room taken days ago* if the
phone app let you pick from the gallery — that photo file still exists, and
nothing about the token prevents attaching it to today's echo. The second
half of the defense is `ImagePicker(source: ImageSource.camera)` with no
gallery affordance rendered at all: the photo must be taken *in the moment
of clearing*, full stop. Neither half is sufficient alone.

## Failure modes handled

- **Publish failure never blocks arming, but never grants a silent pass
  either.** `_gate.py`'s due-check is pure local date/log arithmetic; the
  lock arms on schedule regardless of network state. If the challenge can't
  be published, the lock still shows — with an honest "sync unavailable"
  status and the bounded escape hatch (see below) as the only way past it.
  An earlier draft of this module had the gate silently skip arming and
  auto-log a zero-effort pass whenever Firebase looked unreachable; that was
  an unbounded exploit (block `firebaseio.com` in `/etc/hosts` forever, tidy
  never again) and was removed.
- **`ConfigError` is not a `RemoteSyncError`.** Caught explicitly everywhere
  `RemoteSyncError` is, per diet-guard's own documented gotcha.
- **Size-capped photos, checked on both ends.** The phone re-encodes at a
  lower JPEG quality before upload; the PC independently rejects anything
  over `MAX_EVIDENCE_PHOTO_BYTES` after decoding, so a stale app build or a
  stray upload can never write an unbounded blob to disk.
