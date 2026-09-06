"""The current-zone pointer: a plain state file, not a forward-only history.

Unlike ``.zone_list`` (an edit history), the cursor is a single mutable
pointer -- it only ever answers "which zone is assigned right now", advanced
exactly once per accepted clear.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING

from home_guard._constants import ZONE_CURSOR_FILE
from home_guard._zone_list import (
    ZoneListEntry,
    load_zone_list_entries,
    zone_list_for_day,
)

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

_logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ZoneCursor:
    """The persisted rotation pointer."""

    index: int
    advanced_at: str | None
    last_slot: str | None


def load_cursor(path: Path | None = None) -> ZoneCursor:
    """Read the cursor, defaulting to index 0 if missing/corrupt."""
    target = path if path is not None else ZONE_CURSOR_FILE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ZoneCursor(index=0, advanced_at=None, last_slot=None)
    except (OSError, json.JSONDecodeError) as exc:
        _logger.warning("could not read zone cursor %s: %s", target, exc)
        return ZoneCursor(index=0, advanced_at=None, last_slot=None)
    if not isinstance(raw, dict):
        return ZoneCursor(index=0, advanced_at=None, last_slot=None)
    index = raw.get("index")
    if not isinstance(index, int) or index < 0:
        index = 0
    return ZoneCursor(
        index=index,
        advanced_at=raw.get("advanced_at"),
        last_slot=raw.get("last_slot"),
    )


def _write_cursor(cursor: ZoneCursor, path: Path) -> None:
    payload = {
        "v": _SCHEMA_VERSION,
        "index": cursor.index,
        "advanced_at": cursor.advanced_at,
        "last_slot": cursor.last_slot,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def current_zone(
    now: datetime,
    *,
    cursor: ZoneCursor | None = None,
    zone_entries: tuple[ZoneListEntry, ...] | None = None,
    cursor_path: Path | None = None,
    zone_list_path: Path | None = None,
) -> str:
    """Return the zone currently assigned, resolved against today's list.

    The index is taken modulo *today's* zone-list length, so a rotation that
    shrank since the cursor last advanced still resolves to something valid
    instead of raising.
    """
    resolved_cursor = cursor if cursor is not None else load_cursor(cursor_path)
    entries = (
        zone_entries
        if zone_entries is not None
        else load_zone_list_entries(zone_list_path)
    )
    day = now.strftime("%Y-%m-%d")
    zones = zone_list_for_day(entries, day)
    return zones[resolved_cursor.index % len(zones)]


def advance(
    now: datetime,
    slot_key: str,
    *,
    zone_entries: tuple[ZoneListEntry, ...] | None = None,
    cursor_path: Path | None = None,
    zone_list_path: Path | None = None,
) -> ZoneCursor:
    """Advance the cursor to the next zone, idempotently per ``slot_key``.

    Called **only** on an accepted clear -- never on a read, never
    speculatively. A duplicate call for a ``slot_key`` already recorded as
    the last advance is a no-op, so a poller that fires the accept path
    twice for the same evidence can't double-advance the rotation.
    """
    target_cursor_path = cursor_path if cursor_path is not None else ZONE_CURSOR_FILE
    existing = load_cursor(target_cursor_path)
    if existing.last_slot == slot_key:
        return existing
    entries = (
        zone_entries
        if zone_entries is not None
        else load_zone_list_entries(zone_list_path)
    )
    day = now.strftime("%Y-%m-%d")
    zones = zone_list_for_day(entries, day)
    updated = ZoneCursor(
        index=(existing.index + 1) % len(zones),
        advanced_at=now.isoformat(),
        last_slot=slot_key,
    )
    _write_cursor(updated, target_cursor_path)
    return updated


def seed_default(
    *,
    cursor_path: Path | None = None,
) -> ZoneCursor:
    """Seed the cursor at index 0 if no cursor file exists yet. Idempotent."""
    target = cursor_path if cursor_path is not None else ZONE_CURSOR_FILE
    if target.is_file():
        return load_cursor(target)
    cursor = ZoneCursor(index=0, advanced_at=None, last_slot=None)
    _write_cursor(cursor, target)
    return cursor
