"""The clear/escape log: HMAC-signed, asymmetrically verified.

Two entry kinds, following the same asymmetric idiom as leetcode-guard's
credit/charge ledger split and diet-guard's own HMAC-signed food log:

* ``clear`` entries **grant** something (an unlock + a zone-rotation
  advance) on the strength of a verified photo, so one that fails HMAC
  verification does not count -- a hand-edited JSON file cannot buy a pass.
* ``escape`` entries **also grant** something (an unlock, but no zone
  rotation -- the zone stays assigned and dirty), on the strength of a
  bounded, justified, rate-limited use of the escape hatch (see
  ``_escape_hatch.py``). They count regardless of signature state, because
  their abuse resistance is the hatch's own rolling budget and escalating
  lockout, not this log's HMAC -- discarding an unverifiable-but-genuinely
  budget-checked escape would just be a second, redundant gate.

There is deliberately no automatic, no-justification third kind. An earlier
draft of this module logged a silent "incident" entry whenever Firebase was
merely unreachable, which excused a slot with no budget and no record a
human ever reviewed -- exploitable forever by simply blocking
``firebaseio.com``. Every non-photo grant now goes through the hatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING, Any, Final, Literal

from gatelock.log_integrity import compute_entry_hmac, verify_entry_hmac

from home_guard._constants import HMAC_KEY_FILE
from home_guard._log_store import append_entry, read_raw_log

if TYPE_CHECKING:
    from pathlib import Path

    from home_guard._clear_photos import PhotoRef

_logger = logging.getLogger(__name__)

EntryKind = Literal["clear", "escape"]

_HMAC_KEY_FILE: Final = HMAC_KEY_FILE


def _hmac_key_available(key_file: Path) -> bool:
    return key_file.is_file()


def is_valid_clear_entry(
    entry: dict[str, Any], *, key_file: Path | None = None
) -> bool:
    """Whether a ``clear`` entry's HMAC verifies (or no key exists to check).

    Mirrors diet-guard's ``verify_entry_hmac(entry) if "hmac" in entry else
    not _hmac_key_available()`` discriminator: an entry signed before the key
    ever existed isn't a forgery, but once a key exists every clear entry
    must carry a matching signature.
    """
    target = key_file if key_file is not None else _HMAC_KEY_FILE
    if "hmac" not in entry:
        return not _hmac_key_available(target)
    return verify_entry_hmac(entry, key_file=target)


def _signed_entry(payload: dict[str, Any], *, key_file: Path) -> dict[str, Any]:
    signature = compute_entry_hmac(payload, key_file=key_file)
    if signature is None:
        return dict(payload)
    return {**payload, "hmac": signature}


@dataclass(frozen=True)
class ClearEntryData:
    """What a verified ``clear`` entry records about the slot it satisfies."""

    slot: str
    zone: str
    device: str
    photos: tuple[PhotoRef, ...]
    """One or more photos. A clean is however many shots it took."""

    token: str


def append_clear_entry(
    data: ClearEntryData,
    *,
    now: datetime | None = None,
    key_file: Path | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Sign and append a ``clear`` entry. Returns the stored entry dict."""
    reference = now if now is not None else datetime.now(tz=UTC)
    target_key = key_file if key_file is not None else _HMAC_KEY_FILE
    # New entries carry `photos` and never the legacy `photo_path`/
    # `photo_bytes`. Writing both would put two competing answers to "which
    # photo is authoritative" inside a signed record; read either shape with
    # _clear_photos.photos_of instead.
    payload = {
        "kind": "clear",
        "slot": data.slot,
        "zone": data.zone,
        "device": data.device,
        "logged_at": reference.isoformat(),
        "photos": [{"path": p.path, "bytes": p.bytes_on_disk} for p in data.photos],
        "photo_count": len(data.photos),
        "token": data.token,
    }
    entry = _signed_entry(payload, key_file=target_key)
    append_entry(entry, reference.strftime("%Y-%m-%d"), log_path)
    return entry


@dataclass(frozen=True)
class EscapeEntryData:
    """What an ``escape`` entry records about the slot it satisfies."""

    slot: str
    zone: str
    reason: str


def append_escape_entry(
    data: EscapeEntryData,
    *,
    now: datetime | None = None,
    key_file: Path | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Sign and append an ``escape`` entry (counts even if unverifiable).

    Call only after :mod:`home_guard._escape_hatch` has already validated the
    justification and recorded the use against its own rolling budget --
    that budget, not this signature, is what bounds abuse.
    """
    reference = now if now is not None else datetime.now(tz=UTC)
    target_key = key_file if key_file is not None else _HMAC_KEY_FILE
    payload = {
        "kind": "escape",
        "slot": data.slot,
        "zone": data.zone,
        "reason": data.reason,
        "logged_at": reference.isoformat(),
    }
    entry = _signed_entry(payload, key_file=target_key)
    append_entry(entry, reference.strftime("%Y-%m-%d"), log_path)
    return entry


def cleared_slots_today(
    day: str,
    *,
    key_file: Path | None = None,
    log_path: Path | None = None,
) -> frozenset[str]:
    """Return the set of slot keys satisfied today (valid ``clear`` OR any ``escape``).

    An ``escape`` always counts (its own budget bounds abuse); a ``clear``
    only counts if it passes :func:`is_valid_clear_entry`.
    """
    target_key = key_file if key_file is not None else _HMAC_KEY_FILE
    log = read_raw_log(log_path)
    satisfied: set[str] = set()
    for entry in log.get(day, []):
        slot = entry.get("slot")
        if not isinstance(slot, str):
            continue
        kind = entry.get("kind")
        if kind == "escape" or (
            kind == "clear" and is_valid_clear_entry(entry, key_file=target_key)
        ):
            satisfied.add(slot)
    return frozenset(satisfied)


def recent_entries(
    limit: int = 20,
    *,
    log_path: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return the most recent ``limit`` entries across all days, newest first."""
    log = read_raw_log(log_path)
    flattened = [
        entry for day in sorted(log, reverse=True) for entry in reversed(log[day])
    ]
    return tuple(flattened[:limit])
