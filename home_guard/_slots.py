"""Pure, clock/IO-free slot arithmetic. Mirrors diet-guard's ``_slots.py``.

A "slot" is one scheduled zone-clear check per day, identified by the hour it
opens. Keeping this module free of file IO and wall-clock reads means the
due/missing logic can be tested exhaustively without any fake filesystem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from home_guard._constants import (
    GATE_DAY_START_HOUR,
    GATE_SLOT_INTERVAL_HOURS,
    GATE_WINDOW_END_HOUR,
)

if TYPE_CHECKING:
    from datetime import datetime


def slot_hours(
    *,
    day_start_hour: int = GATE_DAY_START_HOUR,
    interval_hours: int = GATE_SLOT_INTERVAL_HOURS,
    window_end_hour: int = GATE_WINDOW_END_HOUR,
) -> tuple[int, ...]:
    """Return the hours (0-23) at which a slot opens each day.

    Evenly spaced from ``day_start_hour``, stepping by ``interval_hours``,
    stopping before ``window_end_hour``. With the defaults (start 8,
    interval 24) this is a single slot: ``(8,)``.
    """
    hours = []
    hour = day_start_hour
    while hour < window_end_hour:
        hours.append(hour)
        hour += interval_hours
    return tuple(hours)


def within_enforcement_window(
    now: datetime,
    *,
    day_start_hour: int = GATE_DAY_START_HOUR,
    window_end_hour: int = GATE_WINDOW_END_HOUR,
) -> bool:
    """Whether ``now`` falls inside the hours the gate is allowed to fire."""
    return day_start_hour <= now.hour < window_end_hour


def elapsed_slots(
    now: datetime,
    *,
    day_start_hour: int = GATE_DAY_START_HOUR,
    interval_hours: int = GATE_SLOT_INTERVAL_HOURS,
    window_end_hour: int = GATE_WINDOW_END_HOUR,
) -> tuple[str, ...]:
    """Return today's slot keys (``HHMM``) whose hour has already passed.

    Empty outside :func:`within_enforcement_window`, since a slot that has
    not opened yet cannot be "elapsed".
    """
    if not within_enforcement_window(
        now, day_start_hour=day_start_hour, window_end_hour=window_end_hour
    ):
        return ()
    hours = slot_hours(
        day_start_hour=day_start_hour,
        interval_hours=interval_hours,
        window_end_hour=window_end_hour,
    )
    return tuple(f"{hour:02d}00" for hour in hours if hour <= now.hour)


def missing_slots(
    now: datetime,
    cleared_slots_today: frozenset[str],
    *,
    day_start_hour: int = GATE_DAY_START_HOUR,
    interval_hours: int = GATE_SLOT_INTERVAL_HOURS,
    window_end_hour: int = GATE_WINDOW_END_HOUR,
) -> tuple[str, ...]:
    """Return elapsed slots not yet present in ``cleared_slots_today``."""
    elapsed = elapsed_slots(
        now,
        day_start_hour=day_start_hour,
        interval_hours=interval_hours,
        window_end_hour=window_end_hour,
    )
    return tuple(slot for slot in elapsed if slot not in cleared_slots_today)
