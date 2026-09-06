"""Tests for the forward-only zone-list history."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from home_guard._constants import DEFAULT_ZONES
from home_guard._zone_list import (
    load_zone_list_entries,
    record_zone_list_change,
    seed_default,
    zone_list_for_day,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_zone_list_entries(tmp_path / "missing") == ()


def test_load_corrupt_file_returns_empty(tmp_path: Path) -> None:
    target = tmp_path / ".zone_list"
    target.write_text("not json", encoding="utf-8")
    assert load_zone_list_entries(target) == ()


def test_zone_list_for_day_no_entries_falls_back_to_default() -> None:
    assert zone_list_for_day((), "2026-09-06") == DEFAULT_ZONES


def test_seed_default_writes_epoch_entry(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    entries = seed_default(path=path, now=datetime(2026, 9, 6, tzinfo=UTC))
    assert len(entries) == 1
    assert entries[0].effective_from == "1970-01-01"
    assert entries[0].zones == DEFAULT_ZONES


def test_seed_default_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    first = seed_default(path=path)
    record_zone_list_change(("garage",), effective_from="2026-09-01", path=path)
    second = seed_default(path=path)
    # seed_default must not clobber an already-existing (edited) history.
    assert second != first
    assert any(e.zones == ("garage",) for e in second)


def test_record_change_is_forward_only(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    record_zone_list_change(("desk",), effective_from="2026-09-01", path=path)
    record_zone_list_change(("desk", "garage"), effective_from="2026-09-05", path=path)
    entries = load_zone_list_entries(path)
    # A day before the second edit still sees the old list.
    assert zone_list_for_day(entries, "2026-09-03") == ("desk",)
    # On/after the second edit, the new list applies.
    assert zone_list_for_day(entries, "2026-09-05") == ("desk", "garage")
    assert zone_list_for_day(entries, "2026-09-10") == ("desk", "garage")


def test_record_change_same_day_replaces_not_duplicates(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    record_zone_list_change(("desk",), effective_from="2026-09-01", path=path)
    record_zone_list_change(("desk", "garage"), effective_from="2026-09-01", path=path)
    entries = load_zone_list_entries(path)
    assert len(entries) == 1
    assert entries[0].zones == ("desk", "garage")


def test_record_change_rejects_empty_zones(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    with pytest.raises(ValueError, match="at least one zone"):
        record_zone_list_change((), effective_from="2026-09-01", path=path)


def test_load_ignores_malformed_entries(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    path.write_text(
        '{"v": 1, "e": {"2026-09-01": {"zones": "not-a-list"}}}', encoding="utf-8"
    )
    assert load_zone_list_entries(path) == ()


def test_load_non_dict_top_level_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    path.write_text("[]", encoding="utf-8")
    assert load_zone_list_entries(path) == ()


def test_load_missing_entries_key_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    path.write_text('{"v": 1}', encoding="utf-8")
    assert load_zone_list_entries(path) == ()


def test_load_ignores_non_dict_entry_value(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    path.write_text('{"v": 1, "e": {"2026-09-01": "not-a-dict"}}', encoding="utf-8")
    assert load_zone_list_entries(path) == ()


def test_load_ignores_entry_with_only_blank_zones(tmp_path: Path) -> None:
    path = tmp_path / ".zone_list"
    path.write_text(
        '{"v": 1, "e": {"2026-09-01": {"zones": ["", "   "], "t": "x"}}}',
        encoding="utf-8",
    )
    assert load_zone_list_entries(path) == ()
