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
from home_guard._log import ClearEntryData, append_clear_entry
from home_guard._paths import resolve_paths
from home_guard._sync_challenge import publish_challenge
from home_guard._sync_evidence import drain_evidence, save_evidence_photo
from home_guard._zone_cursor import advance

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
    photo_path: Path | None


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
    reference = now if now is not None else datetime.now(tz=UTC)
    resolved = resolve_paths(paths)
    verification = verify_evidence(
        payload, path=resolved.challenge_path, key_file=resolved.challenge_key_file
    )
    if not verification.accepted or verification.record is None:
        return AcceptResult(accepted=False, reason=verification.reason, photo_path=None)
    record = verification.record

    photo_path = save_evidence_photo(payload, photos_dir=resolved.photos_dir)
    if photo_path is None:
        return AcceptResult(accepted=False, reason="photo_invalid", photo_path=None)

    device = payload.get("device_id")
    photo_bytes = photo_path.stat().st_size
    append_clear_entry(
        ClearEntryData(
            slot=record.slot,
            zone=record.zone,
            device=device if isinstance(device, str) else "unknown",
            photo_path=str(photo_path),
            photo_bytes=photo_bytes,
            token=record.token,
        ),
        now=reference,
        key_file=resolved.log_key_file,
        log_path=resolved.log_path,
    )
    advance(
        reference,
        f"{record.day}:{record.slot}",
        cursor_path=resolved.zone_cursor_path,
        zone_list_path=resolved.zone_list_path,
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
    return AcceptResult(accepted=True, reason=None, photo_path=photo_path)
