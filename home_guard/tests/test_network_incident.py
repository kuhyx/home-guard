"""Tests for the best-effort mint-and-publish attempt.

Every path is passed explicitly (tmp_path-rooted) rather than relying on
module-level defaults, so a bug here can never write into the real
``~/.local/share/home_guard`` state -- see mistakes.md's redirect rule.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import home_guard._network_incident as incident_module
from home_guard._network_incident import prepare_slot
from home_guard._paths import HomeGuardPaths
from home_guard._zone_list import record_zone_list_change

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _paths(tmp_path: Path) -> HomeGuardPaths:
    return HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
        zone_cursor_path=tmp_path / ".zone_cursor",
        zone_list_path=tmp_path / ".zone_list",
    )


def test_prepare_slot_reports_success_when_publish_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=paths.zone_list_path
    )
    monkeypatch.setattr(incident_module, "publish_challenge", lambda _record: True)
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    attempt = prepare_slot(now, "0800", paths=paths)
    assert attempt.zone == "desk"
    assert attempt.published
    assert attempt.reachability is None


def test_prepare_slot_reports_reachability_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=paths.zone_list_path
    )
    monkeypatch.setattr(incident_module, "publish_challenge", lambda _record: False)
    monkeypatch.setattr(
        incident_module, "classify_reachability", lambda: "remote_unreachable"
    )
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    attempt = prepare_slot(now, "0800", paths=paths)
    assert not attempt.published
    assert attempt.reachability == "remote_unreachable"


def test_prepare_slot_is_idempotent_across_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=paths.zone_list_path
    )
    monkeypatch.setattr(incident_module, "publish_challenge", lambda _record: True)
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    first = prepare_slot(now, "0800", paths=paths)
    second = prepare_slot(now, "0800", paths=paths)
    assert first.challenge.token == second.challenge.token
