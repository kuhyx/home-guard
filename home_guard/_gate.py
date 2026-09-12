"""Whether the gate is due, and for which zone. Mirrors diet_guard/_gate.py.

The one function the systemd-fired ``python -m home_guard gate`` calls
before opening the lock. Every path/key-file argument is optional and
defaults to the real on-disk locations from ``_constants.py``; tests always
override them so a bug here can never write into real user state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import freedays

from home_guard._log import cleared_slots_today
from home_guard._paths import HomeGuardPaths
from home_guard._slots import missing_slots
from home_guard._zone_cursor import current_zone

if TYPE_CHECKING:
    from pathlib import Path


def _now_local(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(tz=UTC).astimezone()


def due_slots(
    now: datetime | None = None,
    *,
    log_key_file: Path | None = None,
    log_path: Path | None = None,
    free_days_path: Path | None = None,
) -> tuple[str, ...]:
    """Today's elapsed-but-uncleared slot keys, ascending.

    Empty on a free day: the shared pool stands every gate down, so there is
    nothing due and nothing to say about it. Checked first and cheaply --
    ``is_free_day`` reads one local file and never the network, so a gate
    fired by a systemd timer cannot hang here.
    """
    reference = _now_local(now)
    if freedays.is_free_day(reference.date(), log_path=free_days_path):
        return ()
    day = reference.strftime("%Y-%m-%d")
    cleared = cleared_slots_today(day, key_file=log_key_file, log_path=log_path)
    return missing_slots(reference, cleared)


def gate_is_due(
    now: datetime | None = None,
    *,
    log_key_file: Path | None = None,
    log_path: Path | None = None,
    free_days_path: Path | None = None,
) -> bool:
    """Whether any slot has elapsed today without a satisfying log entry."""
    return bool(
        due_slots(
            now,
            log_key_file=log_key_file,
            log_path=log_path,
            free_days_path=free_days_path,
        )
    )


def gate_message(
    now: datetime | None = None,
    *,
    zone_cursor_path: Path | None = None,
    zone_list_path: Path | None = None,
) -> str:
    """Human-facing message naming the zone, not just the slot."""
    reference = _now_local(now)
    zone = current_zone(
        reference,
        paths=HomeGuardPaths(
            zone_cursor_path=zone_cursor_path, zone_list_path=zone_list_path
        ),
    )
    return f"Clear the {zone} to unlock."
