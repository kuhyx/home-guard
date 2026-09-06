"""Mint and verify per-slot challenges: the anti-replay mechanism.

**Publish-then-echo, no secret on the phone.** The PC mints a random token
per (day, slot), keeps it as the sole local authority, and publishes a copy
to Firebase RTDB. The phone echoes the token back verbatim alongside its
photo upload; the PC accepts only if the echoed token matches what it itself
issued and has not already been consumed. No shared secret ever has to
reach the phone, and no image-pixel content is graded -- this only proves
"the phone attested to this specific, single-use challenge", which is all
the family's self-discipline threat model needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import secrets
from typing import TYPE_CHECKING, Any, Literal

from home_guard._challenge_store import ChallengeRecord, get_challenge, put_challenge
from home_guard._paths import resolve_paths

if TYPE_CHECKING:
    from pathlib import Path

    from home_guard._paths import HomeGuardPaths


RejectReason = Literal[
    "no_challenge", "already_consumed", "token_mismatch", "zone_mismatch"
]


@dataclass(frozen=True)
class VerifyResult:
    """The outcome of checking one evidence payload against local state."""

    accepted: bool
    reason: RejectReason | None
    record: ChallengeRecord | None


def mint_challenge(
    *,
    day: str,
    slot: str,
    zone: str,
    now: datetime | None = None,
    paths: HomeGuardPaths | None = None,
) -> ChallengeRecord:
    """Return the challenge for ``(day, slot)``, minting one if none exists.

    Idempotent: a slot's token is minted exactly once and never reissued, so
    a phone that fetches the challenge twice (e.g. a retried publish) still
    sees the same token, and an already-consumed slot's record is returned
    unchanged rather than silently replaced.
    """
    resolved = resolve_paths(paths)
    existing = get_challenge(
        day, slot, path=resolved.challenge_path, key_file=resolved.challenge_key_file
    )
    if existing is not None:
        return existing
    reference = now if now is not None else datetime.now(tz=UTC)
    record = ChallengeRecord(
        day=day,
        slot=slot,
        zone=zone,
        token=secrets.token_urlsafe(24),
        issued_at=reference.isoformat(),
        consumed=False,
    )
    put_challenge(
        record, path=resolved.challenge_path, key_file=resolved.challenge_key_file
    )
    return record


def verify_evidence(
    payload: dict[str, Any],
    *,
    path: Path | None = None,
    key_file: Path | None = None,
) -> VerifyResult:
    """Check an evidence payload's echoed token against local state.

    Checked against the zone **as recorded in the challenge at issue time**,
    not a freshly-read current zone, so a rotation change mid-flight cannot
    be exploited in either direction. Does not mutate state -- call
    :func:`consume_challenge` separately once the caller has also done
    whatever else an accept requires (log entry, cursor advance), so a crash
    between verification and those side effects cannot silently consume a
    challenge with nothing to show for it.
    """
    day = payload.get("day")
    slot = payload.get("slot")
    if not isinstance(day, str) or not isinstance(slot, str):
        return VerifyResult(accepted=False, reason="no_challenge", record=None)
    record = get_challenge(day, slot, path=path, key_file=key_file)
    if record is None:
        return VerifyResult(accepted=False, reason="no_challenge", record=None)
    if record.consumed:
        return VerifyResult(accepted=False, reason="already_consumed", record=record)
    if payload.get("token") != record.token:
        return VerifyResult(accepted=False, reason="token_mismatch", record=record)
    if payload.get("zone") != record.zone:
        return VerifyResult(accepted=False, reason="zone_mismatch", record=record)
    return VerifyResult(accepted=True, reason=None, record=record)


def consume_challenge(
    record: ChallengeRecord,
    *,
    path: Path | None = None,
    key_file: Path | None = None,
) -> None:
    """Mark a record consumed. Call only after every accept side effect lands."""
    consumed = ChallengeRecord(
        day=record.day,
        slot=record.slot,
        zone=record.zone,
        token=record.token,
        issued_at=record.issued_at,
        consumed=True,
    )
    put_challenge(consumed, path=path, key_file=key_file)
