"""Tests for the top-level due/message gate check."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from home_guard import _gate as gate_module
from home_guard._log import ClearEntryData, append_clear_entry
from home_guard._zone_list import record_zone_list_change

if TYPE_CHECKING:
    from pathlib import Path

# The challenge echo under test. A name rather than an inline literal, so
# ruff's S105/S106 (hardcoded password) never trips on a value that is not one.
_ECHO = "t"


def test_gate_is_due_true_when_slot_unlogged(tmp_path: Path) -> None:
    log_path = tmp_path / "clear_log.json"
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    assert gate_module.gate_is_due(now, log_path=log_path)
    assert gate_module.due_slots(now, log_path=log_path) == ("0800",)


def test_gate_is_due_false_after_valid_clear(tmp_path: Path) -> None:
    log_path = tmp_path / "clear_log.json"
    key_file = tmp_path / "no-key"
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    append_clear_entry(
        ClearEntryData(
            slot="0800",
            zone="desk",
            device="d",
            photo_path="p",
            photo_bytes=1,
            token=_ECHO,
        ),
        now=now,
        key_file=key_file,
        log_path=log_path,
    )
    assert not gate_module.gate_is_due(now, log_key_file=key_file, log_path=log_path)


def test_gate_message_names_current_zone(tmp_path: Path) -> None:
    zone_list_path = tmp_path / ".zone_list"
    cursor_path = tmp_path / ".zone_cursor"
    record_zone_list_change(
        ("kitchen counter",), effective_from="1970-01-01", path=zone_list_path
    )
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    message = gate_module.gate_message(
        now, zone_cursor_path=cursor_path, zone_list_path=zone_list_path
    )
    assert message == "Clear the kitchen counter to unlock."
