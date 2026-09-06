"""Tests for the CLI dispatch and each subcommand."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from home_guard._cli import build_parser, main
import home_guard._cli_gate as cli_gate_module
from home_guard._cli_init import cmd_init
from home_guard._cli_status import cmd_status
from home_guard._zone_list import load_zone_list_entries

if TYPE_CHECKING:
    from pathlib import Path


def test_build_parser_has_all_subcommands() -> None:
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_main_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_cmd_init_seeds_zone_list_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import home_guard._zone_cursor as cursor_module
    import home_guard._zone_list as zone_list_module

    zone_list_path = tmp_path / ".zone_list"
    cursor_path = tmp_path / ".zone_cursor"
    monkeypatch.setattr(zone_list_module, "ZONE_LIST_FILE", zone_list_path)
    monkeypatch.setattr(cursor_module, "ZONE_CURSOR_FILE", cursor_path)
    args = build_parser().parse_args(["init", "--zones", "desk", "garage"])
    assert cmd_init(args) == 0
    entries = load_zone_list_entries(zone_list_path)
    assert entries[0].zones == ("desk", "garage")
    # Re-running init must not overwrite the already-seeded rotation.
    assert cmd_init(args) == 0
    assert load_zone_list_entries(zone_list_path) == entries


def test_cmd_status_prints_due_state(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import home_guard._cli_status as cli_status_module

    monkeypatch.setattr(cli_status_module, "due_slots", lambda *_a, **_k: ("0800",))
    monkeypatch.setattr(
        cli_status_module, "gate_message", lambda *_a, **_k: "Clear the desk to unlock."
    )
    args = build_parser().parse_args(["status"])
    assert cmd_status(args) == 0
    captured = capsys.readouterr()
    assert "0800" in captured.out


def test_cmd_gate_nothing_due_does_not_construct_a_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_gate_module, "due_slots", lambda _now: ())
    args = build_parser().parse_args(["gate"])
    assert cli_gate_module.cmd_gate(args) == 0


def test_main_dispatches_to_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import home_guard._cli_status as cli_status_module

    monkeypatch.setattr(cli_status_module, "due_slots", lambda *_a, **_k: ())
    assert main(["status"]) == 0
    assert "nothing due" in capsys.readouterr().out


def test_cmd_gate_arms_when_due(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_gate_module, "due_slots", lambda _now: ("0800",))
    monkeypatch.setattr(cli_gate_module, "wait_for_x_server", lambda: True)
    constructed = {}

    class _FakeGuard:
        def __init__(self, *, slot: str, demo_mode: bool) -> None:
            constructed["slot"] = slot
            constructed["demo_mode"] = demo_mode

        def run(self) -> None:
            constructed["ran"] = True

    monkeypatch.setattr(cli_gate_module, "HomeGuardGuard", _FakeGuard)
    args = build_parser().parse_args(["gate", "--demo"])
    assert cli_gate_module.cmd_gate(args) == 0
    assert constructed == {"slot": "0800", "demo_mode": True, "ran": True}


def test_cmd_gate_gives_up_without_an_x_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_gate_module, "due_slots", lambda _now: ("0800",))
    monkeypatch.setattr(cli_gate_module, "wait_for_x_server", lambda: False)
    args = build_parser().parse_args(["gate"])
    assert cli_gate_module.cmd_gate(args) == 1
