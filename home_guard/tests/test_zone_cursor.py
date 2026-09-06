"""Tests for the plain current-zone pointer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from home_guard._zone_cursor import advance, current_zone, load_cursor, seed_default
from home_guard._zone_list import record_zone_list_change

if TYPE_CHECKING:
    from pathlib import Path


def test_load_missing_cursor_defaults_to_zero(tmp_path: Path) -> None:
    cursor = load_cursor(tmp_path / "missing")
    assert cursor.index == 0
    assert cursor.last_slot is None


def test_load_corrupt_cursor_defaults_to_zero(tmp_path: Path) -> None:
    path = tmp_path / ".zone_cursor"
    path.write_text("not json", encoding="utf-8")
    assert load_cursor(path).index == 0


def test_load_negative_index_defaults_to_zero(tmp_path: Path) -> None:
    path = tmp_path / ".zone_cursor"
    path.write_text('{"index": -3}', encoding="utf-8")
    assert load_cursor(path).index == 0


def test_load_non_dict_defaults_to_zero(tmp_path: Path) -> None:
    path = tmp_path / ".zone_cursor"
    path.write_text("[]", encoding="utf-8")
    assert load_cursor(path).index == 0


def test_seed_default_creates_file_once(tmp_path: Path) -> None:
    path = tmp_path / ".zone_cursor"
    seed_default(cursor_path=path)
    assert path.is_file()
    path.write_text(
        '{"index": 5, "advanced_at": null, "last_slot": null}', encoding="utf-8"
    )
    # Re-seeding must not clobber an existing file.
    seed_default(cursor_path=path)
    assert load_cursor(path).index == 5


def test_current_zone_uses_default_zones(tmp_path: Path) -> None:
    zone_list_path = tmp_path / ".zone_list"
    cursor_path = tmp_path / ".zone_cursor"
    record_zone_list_change(
        ("desk", "kitchen"), effective_from="1970-01-01", path=zone_list_path
    )
    zone = current_zone(
        datetime(2026, 9, 6, tzinfo=UTC),
        cursor_path=cursor_path,
        zone_list_path=zone_list_path,
    )
    assert zone == "desk"


def test_advance_moves_to_next_zone_and_wraps(tmp_path: Path) -> None:
    zone_list_path = tmp_path / ".zone_list"
    cursor_path = tmp_path / ".zone_cursor"
    record_zone_list_change(
        ("desk", "kitchen"), effective_from="1970-01-01", path=zone_list_path
    )
    now = datetime(2026, 9, 6, tzinfo=UTC)
    advance(
        now, "2026-09-06:0800", cursor_path=cursor_path, zone_list_path=zone_list_path
    )
    assert (
        current_zone(now, cursor_path=cursor_path, zone_list_path=zone_list_path)
        == "kitchen"
    )
    advance(
        now, "2026-09-07:0800", cursor_path=cursor_path, zone_list_path=zone_list_path
    )
    assert (
        current_zone(now, cursor_path=cursor_path, zone_list_path=zone_list_path)
        == "desk"
    )


def test_advance_same_slot_key_is_idempotent(tmp_path: Path) -> None:
    zone_list_path = tmp_path / ".zone_list"
    cursor_path = tmp_path / ".zone_cursor"
    record_zone_list_change(
        ("desk", "kitchen"), effective_from="1970-01-01", path=zone_list_path
    )
    now = datetime(2026, 9, 6, tzinfo=UTC)
    advance(now, "slot-a", cursor_path=cursor_path, zone_list_path=zone_list_path)
    first = load_cursor(cursor_path)
    advance(now, "slot-a", cursor_path=cursor_path, zone_list_path=zone_list_path)
    second = load_cursor(cursor_path)
    assert first == second


def test_current_zone_modulo_survives_shrunk_list(tmp_path: Path) -> None:
    zone_list_path = tmp_path / ".zone_list"
    cursor_path = tmp_path / ".zone_cursor"
    record_zone_list_change(
        ("desk", "kitchen", "garage"), effective_from="1970-01-01", path=zone_list_path
    )
    now = datetime(2026, 9, 6, tzinfo=UTC)
    advance(now, "s1", cursor_path=cursor_path, zone_list_path=zone_list_path)
    advance(now, "s2", cursor_path=cursor_path, zone_list_path=zone_list_path)
    # cursor.index is now 2 ("garage"); shrink the list to 2 zones.
    record_zone_list_change(
        ("desk", "kitchen"), effective_from="2026-09-06", path=zone_list_path
    )
    zone = current_zone(now, cursor_path=cursor_path, zone_list_path=zone_list_path)
    assert zone in ("desk", "kitchen")
