"""The full accept pipeline: verify, photo, log, rotate, re-publish, drain.

Wires together every module that has to agree before a slot counts as
cleared. Kept separate from :mod:`home_guard._poller` so the pipeline itself
-- pure aside from disk/RTDB writes, no Tk, no thread pool -- can be tested
directly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from home_guard._challenge import consume_challenge, verify_evidence
from home_guard._clear_photos import PhotoRef
from home_guard._evidence_photos import save_evidence_photos
from home_guard._log import ClearEntryData, append_clear_entry
from home_guard._paths import resolve_paths
from home_guard._sync_challenge import publish_challenge
from home_guard._sync_evidence import drain_evidence
from home_guard._zone_cursor import advance
from home_guard._zone_list import load_zone_list_entries, zone_list_for_day

if TYPE_CHECKING:
    from pathlib import Path

    from crdt_sync import RemoteStore

    from home_guard._paths import HomeGuardPaths

AcceptOutcome = Literal[
    "no_challenge",
    "already_consumed",
    "token_mismatch",
    "zone_mismatch",
    "photo_invalid",
]


@dataclass(frozen=True)
class AcceptResult:
    """The outcome of processing one evidence payload."""

    accepted: bool
    reason: AcceptOutcome | None
    photo_paths: tuple[Path, ...] = ()


def _local(moment: datetime) -> datetime:
    """Local time, so every day string in this module matches the gate's."""
    return moment.astimezone()


def _captured_at(payload: dict[str, Any], fallback: datetime) -> datetime:
    """When the phone says the photos were taken, clamped to sanity.

    A self-reported timestamp is only trusted backwards: it may name an
    earlier day (a session queued while the PC was off), but never a later
    one, which would let a phone with a fast clock pre-satisfy a slot that
    has not happened yet.
    """
    raw = payload.get("captured_at")
    if not isinstance(raw, str) or not raw:
        return fallback
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        return fallback
    local = _local(parsed)
    return min(local, fallback)


def process_evidence(
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
    paths: HomeGuardPaths | None = None,
    drain: bool = True,
    client: RemoteStore | None = None,
) -> AcceptResult:
    """Verify ``payload`` and, if it checks out, grant the slot.

    A rejected payload has no side effects at all -- it is left in place at
    its fixed RTDB path so a legitimate retry can simply overwrite it.
    """
    reference = _local(now if now is not None else datetime.now(tz=UTC))
    resolved = resolve_paths(paths)

    # The day the cleaning HAPPENED, which for a session queued offline is
    # not today. Local, never UTC: _gate.py derives its day with
    # .astimezone(), and _log.py buckets by whatever datetime it is handed,
    # so a UTC-derived day silently files a 00:30 clean under yesterday and
    # the gate never sees it.
    captured = _captured_at(payload, reference)
    day = captured.strftime("%Y-%m-%d")

    entries = load_zone_list_entries(resolved.zone_list_path)
    verification = verify_evidence(
        payload,
        path=resolved.challenge_path,
        key_file=resolved.challenge_key_file,
        allowed_zones=zone_list_for_day(entries, day),
    )
    if not verification.accepted or verification.record is None:
        return AcceptResult(accepted=False, reason=verification.reason)
    record = verification.record

    photo_paths = save_evidence_photos(payload, photos_dir=resolved.photos_dir)
    if not photo_paths:
        return AcceptResult(accepted=False, reason="photo_invalid")

    device = payload.get("device_id")
    cleaned_zone = payload.get("zone")
    append_clear_entry(
        ClearEntryData(
            slot=record.slot,
            zone=cleaned_zone if isinstance(cleaned_zone, str) else record.zone,
            device=device if isinstance(device, str) else "unknown",
            photos=tuple(
                PhotoRef(path=str(p), bytes_on_disk=p.stat().st_size)
                for p in photo_paths
            ),
            token=record.token,
        ),
        # Stamped into the day it was captured, not the day it was drained.
        # cleared_slots_today() only ever reads TODAY's bucket, so a clean
        # done today unlocks today, and one queued from yesterday lands in
        # yesterday's bucket: the record and the rotation advance are kept,
        # but it grants nothing now. That is the whole backdating rule, and
        # it costs no extra code.
        now=captured,
        key_file=resolved.log_key_file,
        log_path=resolved.log_path,
    )
    advance(
        captured,
        f"{record.day}:{record.slot}",
        cleaned_zone=cleaned_zone if isinstance(cleaned_zone, str) else None,
        paths=resolved,
    )
    consume_challenge(
        record, path=resolved.challenge_path, key_file=resolved.challenge_key_file
    )
    if drain:
        # Re-publish the record as consumed BEFORE draining: the phone reads
        # the challenge node to decide whether to offer the camera at all, and
        # the local store is the only place `consumed` was ever flipped.
        # Without this the phone re-offered "Take photo" straight after an
        # accept, the second upload was rejected `already_consumed`, and the
        # app sat in "unconfirmed" for the rest of the day.
        publish_challenge(replace(record, consumed=True), client=client)
        drain_evidence(client=client)
    return AcceptResult(accepted=True, reason=None, photo_paths=photo_paths)
