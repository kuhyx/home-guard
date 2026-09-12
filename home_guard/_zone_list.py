"""Forward-only history of the zone rotation list.

Ported from diet-guard's meal-schedule-history shape. Editing the rotation
(adding "garage", say) must not retroactively change which zone an
already-judged past slot was checked against, so each edit is appended with
an ``effective_from`` day rather than overwriting the current list in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from typing import TYPE_CHECKING

from home_guard._constants import DEFAULT_ZONES, ZONE_LIST_FILE

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ZoneListEntry:
    """One effective-from edit of the rotation list."""

    effective_from: str
    """``YYYY-MM-DD``. This list is in force from this day onward."""

    zones: tuple[str, ...]
    edited_at: str
    """Full ISO timestamp the edit was made, for forensics only."""


def _entry_from_raw(day: str, raw: object) -> ZoneListEntry | None:
    if not isinstance(raw, dict):
        return None
    zones = raw.get("zones")
    edited_at = raw.get("t")
    if not isinstance(zones, list) or not isinstance(edited_at, str):
        return None
    cleaned = tuple(z for z in zones if isinstance(z, str) and z.strip())
    if not cleaned:
        return None
    return ZoneListEntry(effective_from=day, zones=cleaned, edited_at=edited_at)


def entries_from_payload(raw: object) -> tuple[ZoneListEntry, ...] | None:
    """Parse a history payload. ``None`` means "not a history at all".

    Split out of :func:`load_zone_list_entries` so the RTDB transport
    (:mod:`home_guard._sync_zones`) parses the *same* shape with the *same*
    code as the file does -- a second parser is how the two representations
    would drift. ``None`` rather than ``()`` for garbage, so a caller can tell
    "could not read it" from "read it, it was empty".
    """
    if not isinstance(raw, dict):
        return None
    entries_raw = raw.get("e")
    if not isinstance(entries_raw, dict):
        return None
    entries = [
        entry
        for day, raw_entry in entries_raw.items()
        if (entry := _entry_from_raw(day, raw_entry)) is not None
    ]
    return tuple(sorted(entries, key=lambda e: e.effective_from))


def payload_from_entries(entries: tuple[ZoneListEntry, ...]) -> dict[str, object]:
    """Serialise a history to the on-disk/on-wire shape."""
    return {
        "v": _SCHEMA_VERSION,
        "e": {
            e.effective_from: {"zones": list(e.zones), "t": e.edited_at}
            for e in entries
        },
    }


def load_zone_list_entries(path: Path | None = None) -> tuple[ZoneListEntry, ...]:
    """Read every recorded edit, oldest first. Missing/corrupt file -> empty."""
    target = path if path is not None else ZONE_LIST_FILE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except (OSError, json.JSONDecodeError) as exc:
        _logger.warning("could not read zone list history %s: %s", target, exc)
        return ()
    parsed = entries_from_payload(raw)
    return parsed if parsed is not None else ()


def zone_list_for_day(entries: tuple[ZoneListEntry, ...], day: str) -> tuple[str, ...]:
    """Return the rotation list in force on ``day`` (``YYYY-MM-DD``).

    The newest entry whose ``effective_from`` is on or before ``day`` wins.
    No entry at all (never initialized) falls back to :data:`DEFAULT_ZONES`.
    """
    applicable = [e for e in entries if e.effective_from <= day]
    if not applicable:
        return DEFAULT_ZONES
    return max(applicable, key=lambda e: e.effective_from).zones


def write_entries(entries: tuple[ZoneListEntry, ...], path: Path | None = None) -> None:
    """Persist a whole history atomically.

    Public because a merge (:mod:`home_guard._zone_merge`) produces an entire
    history rather than one appended edit, and re-appending each merged entry
    through :func:`record_zone_list_change` would rewrite every ``edited_at``
    and so destroy the very timestamps the merge resolves collisions by.
    """
    target = path if path is not None else ZONE_LIST_FILE
    _write_entries(entries, target)


def _write_entries(entries: tuple[ZoneListEntry, ...], path: Path) -> None:
    payload = payload_from_entries(entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def record_zone_list_change(
    zones: tuple[str, ...],
    *,
    effective_from: str,
    now: datetime | None = None,
    path: Path | None = None,
) -> tuple[ZoneListEntry, ...]:
    """Append a new effective-from edit and persist it. Returns the new history.

    Raises:
        ValueError: ``zones`` is empty.
    """
    if not zones:
        message = "a zone rotation must have at least one zone"
        raise ValueError(message)
    target = path if path is not None else ZONE_LIST_FILE
    reference = now if now is not None else datetime.now(tz=UTC)
    entries = load_zone_list_entries(target)
    # Replace any existing entry for the same effective_from day rather than
    # duplicating it -- an init followed by an init on the same day is a
    # correction, not two competing edits.
    entries = tuple(e for e in entries if e.effective_from != effective_from)
    new_entry = ZoneListEntry(
        effective_from=effective_from,
        zones=zones,
        edited_at=reference.isoformat(),
    )
    updated = tuple(sorted((*entries, new_entry), key=lambda e: e.effective_from))
    _write_entries(updated, target)
    return updated


def seed_default(
    *,
    now: datetime | None = None,
    path: Path | None = None,
) -> tuple[ZoneListEntry, ...]:
    """Seed the zone list at the epoch if no history exists yet.

    Idempotent: does nothing if a history file is already present, so
    re-running ``home_guard init`` never clobbers an edited rotation.
    """
    target = path if path is not None else ZONE_LIST_FILE
    existing = load_zone_list_entries(target)
    if existing:
        return existing
    reference = now if now is not None else datetime.now(tz=UTC)
    epoch_day = "1970-01-01"
    return record_zone_list_change(
        DEFAULT_ZONES, effective_from=epoch_day, now=reference, path=target
    )
