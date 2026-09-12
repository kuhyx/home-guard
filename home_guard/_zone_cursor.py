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
from home_guard._paths import HomeGuardPaths, resolve_paths
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
    paths: HomeGuardPaths | None = None,
) -> str:
    """Return the zone currently assigned, resolved against today's list.

    The index is taken modulo *today's* zone-list length, so a rotation that
    shrank since the cursor last advanced still resolves to something valid
    instead of raising.
    """
    resolved = resolve_paths(paths)
    resolved_cursor = (
        cursor if cursor is not None else load_cursor(resolved.zone_cursor_path)
    )
    entries = (
        zone_entries
        if zone_entries is not None
        else load_zone_list_entries(resolved.zone_list_path)
    )
    day = now.strftime("%Y-%m-%d")
    zones = zone_list_for_day(entries, day)
    return zones[resolved_cursor.index % len(zones)]


def advance(
    now: datetime,
    slot_key: str,
    *,
    cleaned_zone: str | None = None,
    zone_entries: tuple[ZoneListEntry, ...] | None = None,
    paths: HomeGuardPaths | None = None,
) -> ZoneCursor:
    """Advance the cursor past the zone that was actually cleaned.

    Called **only** on an accepted clear -- never on a read, never
    speculatively. A duplicate call for a ``slot_key`` already recorded as
    the last advance is a no-op, so a poller that fires the accept path
    twice for the same evidence can't double-advance the rotation.

    ``cleaned_zone`` is the zone the evidence was actually for, which is not
    necessarily the one the cursor pointed at: you may clean any zone in
    today's rotation, not only the assigned one. The cursor moves to just
    after *that* zone, so the thing you just cleaned is the last to come
    round again. Falls back to a plain +1 when the zone is unknown or is no
    longer in today's list (it may have been removed mid-flight), which is
    exactly the old behaviour.
    """
    resolved = resolve_paths(paths)
    target_cursor_path = (
        resolved.zone_cursor_path
        if resolved.zone_cursor_path is not None
        else ZONE_CURSOR_FILE
    )
    existing = load_cursor(target_cursor_path)
    if existing.last_slot == slot_key:
        return existing
    entries = (
        zone_entries
        if zone_entries is not None
        else load_zone_list_entries(resolved.zone_list_path)
    )
    day = now.strftime("%Y-%m-%d")
    zones = zone_list_for_day(entries, day)
    if cleaned_zone is not None and cleaned_zone in zones:
        next_index = (zones.index(cleaned_zone) + 1) % len(zones)
    else:
        next_index = (existing.index + 1) % len(zones)
    updated = ZoneCursor(
        index=next_index,
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
