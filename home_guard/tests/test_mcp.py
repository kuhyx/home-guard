"""Tests for the read-only MCP server: correct data, and the no-write invariant."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from home_guard._clear_photos import PhotoRef
from home_guard._log import ClearEntryData, append_clear_entry
import home_guard._log_store as log_store_module
from home_guard._mcp import (
    explain_lock,
    get_clear_history,
    get_status,
    get_zone_rotation,
    mcp,
)
import home_guard._zone_cursor as cursor_module
import home_guard._zone_list as zone_list_module
from home_guard._zone_list import record_zone_list_change

if TYPE_CHECKING:
    from pathlib import Path

# The challenge echo under test. A name rather than an inline literal, so
# ruff's S105/S106 (hardcoded password) never trips on a value that is not one.
_ECHO = "tok"


def _redirect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(log_store_module, "CLEAR_LOG_FILE", tmp_path / "clear_log.json")
    monkeypatch.setattr(zone_list_module, "ZONE_LIST_FILE", tmp_path / ".zone_list")
    monkeypatch.setattr(cursor_module, "ZONE_CURSOR_FILE", tmp_path / ".zone_cursor")


def test_get_status_reports_due_slot_and_zone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect(monkeypatch, tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=tmp_path / ".zone_list"
    )
    status = get_status()
    assert status["current_zone"] == "desk"
    assert isinstance(status["gate_is_due"], bool)
    assert isinstance(status["due_slots"], list)


def test_get_zone_rotation_includes_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect(monkeypatch, tmp_path)
    record_zone_list_change(
        ("desk", "kitchen"), effective_from="1970-01-01", path=tmp_path / ".zone_list"
    )
    rotation = get_zone_rotation()
    assert rotation["zones_today"] == ["desk", "kitchen"]
    assert rotation["current_zone"] == "desk"
    assert rotation["history"][0]["zones"] == ["desk", "kitchen"]


def test_get_clear_history_returns_recent_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect(monkeypatch, tmp_path)
    append_clear_entry(
        ClearEntryData(
            slot="0800",
            zone="desk",
            device="phone-1",
            photos=(PhotoRef(path="photos/x.jpg", bytes_on_disk=10),),
            token=_ECHO,
        ),
        now=datetime(2026, 9, 6, 9, tzinfo=UTC),
        key_file=tmp_path / "no-key",
        log_path=tmp_path / "clear_log.json",
    )
    history = get_clear_history(limit=5)
    assert len(history["entries"]) == 1
    assert history["entries"][0]["zone"] == "desk"
    # Photo bytes never leave the log entry as raw content -- only a path.
    assert "photo_b64" not in history["entries"][0]


def test_explain_lock_returns_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _redirect(monkeypatch, tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=tmp_path / ".zone_list"
    )
    result = explain_lock()
    assert "desk" in result["message"]
    assert isinstance(result["gate_is_due"], bool)


@pytest.mark.asyncio
async def test_no_write_tools_registered() -> None:
    """The whole point of home-guard's MCP server: no tool may grant a clear."""
    tools = await mcp.list_tools()
    assert tools, "expected at least the four read tools to be registered"
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
