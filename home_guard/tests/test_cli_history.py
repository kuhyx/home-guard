"""Tests for the ``history`` subcommand."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from home_guard._cli import build_parser


def test_cmd_history_prints_json_lines(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two fake entries should produce two JSON lines, newest first."""
    import home_guard._cli_history as cli_history_module

    fake_entries = [
        {
            "kind": "clear",
            "slot": "0800",
            "zone": "desk",
            "logged_at": "2024-01-02",
        },
        {
            "kind": "escape",
            "slot": "0900",
            "zone": "kitchen",
            "logged_at": "2024-01-01",
        },
    ]
    captured_limit: dict[str, int] = {}

    def fake_recent_entries(
        limit: int = 20, **_kw: object
    ) -> tuple[dict[str, str], ...]:
        captured_limit["limit"] = limit
        if limit == 1:
            return (fake_entries[0],)
        return tuple(fake_entries)

    monkeypatch.setattr(
        cli_history_module, "recent_entries", fake_recent_entries, raising=False
    )

    parser = build_parser()
    args = parser.parse_args(["history"])
    assert cli_history_module.cmd_history(args) == 0
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["slot"] == "0800"
    assert json.loads(lines[1])["slot"] == "0900"


def test_cmd_history_respects_limit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """--limit 1 should pass limit=1 to recent_entries."""
    import home_guard._cli_history as cli_history_module

    captured_limit: dict[str, int] = {}

    def fake_recent_entries(
        limit: int = 20, **_kw: object
    ) -> tuple[dict[str, str], ...]:
        captured_limit["limit"] = limit
        return ({"kind": "clear", "slot": "0800"},)

    monkeypatch.setattr(
        cli_history_module, "recent_entries", fake_recent_entries, raising=False
    )

    parser = build_parser()
    args = parser.parse_args(["history", "--limit", "1"])
    assert args.limit == 1
    cli_history_module.cmd_history(args)
    assert captured_limit["limit"] == 1


def test_cmd_history_empty_log(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Empty log should print the no-clears message."""
    import home_guard._cli_history as cli_history_module

    monkeypatch.setattr(
        cli_history_module, "recent_entries", lambda **_kw: (), raising=False
    )

    parser = build_parser()
    args = parser.parse_args(["history"])
    assert cli_history_module.cmd_history(args) == 0
    assert "no clears or escapes logged yet." in capsys.readouterr().out


def test_history_parser_default_limit() -> None:
    """The history subcommand should default to limit=20."""
    args = build_parser().parse_args(["history"])
    assert args.limit == 20
