"""Tests for pure slot arithmetic."""

from __future__ import annotations

from datetime import UTC, datetime

from home_guard._slots import (
    elapsed_slots,
    missing_slots,
    slot_hours,
    within_enforcement_window,
)


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 6, hour, minute, tzinfo=UTC)


def test_slot_hours_single_daily_slot() -> None:
    assert slot_hours(day_start_hour=8, interval_hours=24, window_end_hour=22) == (8,)


def test_slot_hours_multi_slot_day() -> None:
    assert slot_hours(day_start_hour=8, interval_hours=4, window_end_hour=22) == (
        8,
        12,
        16,
        20,
    )


def test_within_enforcement_window_true_inside() -> None:
    assert within_enforcement_window(_at(9), day_start_hour=8, window_end_hour=22)


def test_within_enforcement_window_false_before_start() -> None:
    assert not within_enforcement_window(_at(7), day_start_hour=8, window_end_hour=22)


def test_within_enforcement_window_false_at_or_after_end() -> None:
    assert not within_enforcement_window(_at(22), day_start_hour=8, window_end_hour=22)


def test_elapsed_slots_empty_before_window() -> None:
    assert elapsed_slots(_at(7), day_start_hour=8, window_end_hour=22) == ()


def test_elapsed_slots_single_slot_after_open() -> None:
    assert elapsed_slots(
        _at(9), day_start_hour=8, interval_hours=24, window_end_hour=22
    ) == ("0800",)


def test_elapsed_slots_multi_slot_day_partial() -> None:
    assert elapsed_slots(
        _at(13), day_start_hour=8, interval_hours=4, window_end_hour=22
    ) == ("0800", "1200")


def test_missing_slots_excludes_cleared() -> None:
    result = missing_slots(
        _at(13),
        frozenset({"0800"}),
        day_start_hour=8,
        interval_hours=4,
        window_end_hour=22,
    )
    assert result == ("1200",)


def test_missing_slots_all_cleared_is_empty() -> None:
    result = missing_slots(
        _at(9),
        frozenset({"0800"}),
        day_start_hour=8,
        interval_hours=24,
        window_end_hour=22,
    )
    assert result == ()
