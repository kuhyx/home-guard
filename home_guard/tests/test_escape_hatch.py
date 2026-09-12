"""Tests for the bounded, justified sync-outage escape hatch."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gatelock import EscapeDraft

from home_guard._escape_hatch import SlotZone, build_tracker, grant_escape
from home_guard._log import cleared_slots_today
from home_guard._paths import HomeGuardPaths

if TYPE_CHECKING:
    from pathlib import Path

_VALID_DRAFT = EscapeDraft(
    reason="Firebase looks down",
    onset="just now",
    severity=3,
    description="x" * 45,
)

_TARGET = SlotZone(slot="0800", zone="desk")


def _hatch_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "path": tmp_path / "escape_history.json",
        "key_file": tmp_path / "no-key",
    }


def test_grant_escape_succeeds_and_logs(tmp_path: Path) -> None:
    hatch = _hatch_paths(tmp_path)
    log_path = tmp_path / "clear_log.json"
    tracker = build_tracker(**hatch)
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    error = grant_escape(
        tracker,
        _VALID_DRAFT,
        _TARGET,
        now=now,
        paths=HomeGuardPaths(log_key_file=hatch["key_file"], log_path=log_path),
    )
    assert error is None
    assert cleared_slots_today(
        "2026-09-06", key_file=hatch["key_file"], log_path=log_path
    ) == frozenset({"0800"})


def test_grant_escape_rejects_invalid_draft(tmp_path: Path) -> None:
    hatch = _hatch_paths(tmp_path)
    tracker = build_tracker(**hatch)
    bad_draft = EscapeDraft(reason="", onset="now", severity=3, description="x" * 45)
    error = grant_escape(
        tracker,
        bad_draft,
        _TARGET,
        paths=HomeGuardPaths(log_path=tmp_path / "clear_log.json"),
    )
    assert error is not None
    assert "problem" in error.lower()


def test_grant_escape_blocked_once_budget_exhausted(tmp_path: Path) -> None:
    hatch = _hatch_paths(tmp_path)
    log_path = tmp_path / "clear_log.json"
    tracker = build_tracker(**hatch)
    # Policy allows 2 uses per 7 days; use it twice, then a third must fail.
    for day in ("2026-09-01", "2026-09-02"):
        now = datetime.fromisoformat(f"{day}T09:00:00+00:00")
        error = grant_escape(
            tracker,
            _VALID_DRAFT,
            _TARGET,
            now=now,
            paths=HomeGuardPaths(log_key_file=hatch["key_file"], log_path=log_path),
        )
        assert error is None
    third = grant_escape(
        tracker,
        _VALID_DRAFT,
        _TARGET,
        now=datetime(2026, 9, 3, 9, tzinfo=UTC),
        paths=HomeGuardPaths(log_key_file=hatch["key_file"], log_path=log_path),
    )
    assert third is not None
    assert "no uses" in third.lower()


def test_grant_escape_reports_when_history_cannot_be_saved(tmp_path: Path) -> None:
    hatch = _hatch_paths(tmp_path)
    # A directory in place of the history file makes EscapeTracker.save()
    # fail with OSError, exercising the "could not save" branch.
    hatch["path"].mkdir()
    tracker = build_tracker(**hatch)
    error = grant_escape(
        tracker,
        _VALID_DRAFT,
        _TARGET,
        paths=HomeGuardPaths(log_path=tmp_path / "clear_log.json"),
    )
    assert error is not None
    assert "could not save" in error.lower()


def test_grant_escape_does_not_rotate_zone(tmp_path: Path) -> None:
    from home_guard._zone_cursor import current_zone
    from home_guard._zone_list import record_zone_list_change

    hatch = _hatch_paths(tmp_path)
    zone_list_path = tmp_path / ".zone_list"
    cursor_path = tmp_path / ".zone_cursor"
    record_zone_list_change(
        ("desk", "kitchen"), effective_from="1970-01-01", path=zone_list_path
    )
    tracker = build_tracker(**hatch)
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    grant_escape(
        tracker,
        _VALID_DRAFT,
        _TARGET,
        now=now,
        paths=HomeGuardPaths(log_path=tmp_path / "clear_log.json"),
    )
    assert (
        current_zone(
            now,
            paths=HomeGuardPaths(
                zone_cursor_path=cursor_path, zone_list_path=zone_list_path
            ),
        )
        == "desk"
    )
