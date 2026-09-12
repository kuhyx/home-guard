"""Tests for ``home_guard zones``: show, edit, and merge the rotation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from home_guard._cli import build_parser
import home_guard._cli_zones as cli_zones_module
import home_guard._zone_list as zone_list_module
from home_guard._zone_list import ZoneListEntry, load_zone_list_entries

if TYPE_CHECKING:
    from pathlib import Path

TODAY = "2026-09-12"


@pytest.fixture
def zone_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the zone list at tmp_path and freeze "today"."""
    path = tmp_path / ".zone_list"
    # Patched in the DEFINING module here on purpose: _cli_zones calls
    # load_zone_list_entries()/record_zone_list_change() with no path
    # argument, so they resolve ZONE_LIST_FILE from their own namespace.
    monkeypatch.setattr(zone_list_module, "ZONE_LIST_FILE", path)
    monkeypatch.setattr(cli_zones_module, "_today", lambda: TODAY)
    # Default to "no network"; individual tests override.
    monkeypatch.setattr(cli_zones_module, "fetch_zone_history", lambda: None)
    monkeypatch.setattr(cli_zones_module, "publish_zone_history", lambda _e: True)
    return path


def _run(*argv: str) -> int:
    args = build_parser().parse_args(["zones", *argv])
    return cli_zones_module.cmd_zones(args)


def test_set_records_the_rotation_from_today(
    zone_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run("--set", "mirror", "washing machine") == 0
    entries = load_zone_list_entries(zone_file)
    assert entries[-1].zones == ("mirror", "washing machine")
    # Today, never the epoch: an edit must not re-judge a past slot.
    assert entries[-1].effective_from == TODAY
    assert "mirror, washing machine" in capsys.readouterr().out


def test_set_strips_blank_zone_names(zone_file: Path) -> None:
    assert _run("--set", "  mirror  ", "   ", "toilet") == 0
    assert load_zone_list_entries(zone_file)[-1].zones == ("mirror", "toilet")


def test_set_refuses_an_all_blank_rotation(
    zone_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run("--set", "   ") == 1
    assert "at least one zone" in capsys.readouterr().out
    assert load_zone_list_entries(zone_file) == ()


def test_set_refuses_a_past_effective_from(
    zone_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Forward-only: you cannot change what a past slot was checked against."""
    assert _run("--set", "mirror", "--effective-from", "2020-01-01") == 1
    assert "forward-only" in capsys.readouterr().out
    assert load_zone_list_entries(zone_file) == ()


def test_set_accepts_a_future_effective_from(zone_file: Path) -> None:
    assert _run("--set", "garage", "--effective-from", "2026-12-01") == 0
    assert load_zone_list_entries(zone_file)[-1].effective_from == "2026-12-01"


def test_listing_prints_today_and_the_history(
    zone_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run("--set", "mirror")
    capsys.readouterr()
    assert _run() == 0
    out = capsys.readouterr().out
    assert f"rotation today ({TODAY})" in out
    assert f"from {TODAY}: mirror" in out


def test_pull_merges_the_phones_edit(
    zone_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    remote = (
        ZoneListEntry(
            effective_from=TODAY,
            zones=("mirror", "toilet"),
            edited_at="2026-09-12T19:00:00+00:00",
        ),
    )
    monkeypatch.setattr(cli_zones_module, "fetch_zone_history", lambda: remote)
    assert _run("--pull") == 0
    assert load_zone_list_entries(zone_file)[-1].zones == ("mirror", "toilet")
    assert "merged edits from the phone" in capsys.readouterr().out


def test_pull_is_quiet_when_already_current(
    zone_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _run("--set", "mirror")
    capsys.readouterr()
    monkeypatch.setattr(
        cli_zones_module,
        "fetch_zone_history",
        lambda: load_zone_list_entries(zone_file),
    )
    assert _run("--pull") == 0
    assert "already up to date" in capsys.readouterr().out


def test_offline_falls_back_to_the_local_rotation(
    zone_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dead network must never stop you reading or editing the rotation."""
    assert _run("--set", "mirror") == 0
    assert "could not read the published rotation" in capsys.readouterr().out
    assert load_zone_list_entries(zone_file)[-1].zones == ("mirror",)


def test_set_reports_a_failed_publish_without_losing_the_edit(
    zone_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli_zones_module, "publish_zone_history", lambda _e: False)
    assert _run("--set", "mirror") == 0
    assert "could not publish to the phone" in capsys.readouterr().out
    assert load_zone_list_entries(zone_file)[-1].zones == ("mirror",)


def test_today_is_local_time() -> None:
    """Matches how _gate.py formats a day; a UTC date would mis-bucket edits."""
    day = cli_zones_module._today()
    assert len(day) == 10
    assert day[4] == "-"


def test_add_appends_to_the_existing_rotation(zone_file: Path) -> None:
    """The verb the rotation is actually edited with: keep what is there."""
    _run("--set", "desk", "kitchen counter")
    assert _run("--add", "mirror", "washbasin") == 0
    assert load_zone_list_entries(zone_file)[-1].zones == (
        "desk",
        "kitchen counter",
        "mirror",
        "washbasin",
    )


def test_add_to_an_unseeded_rotation_extends_the_defaults(zone_file: Path) -> None:
    # No history yet resolves to DEFAULT_ZONES, so --add must build on those
    # rather than silently starting from nothing.
    assert _run("--add", "mirror") == 0
    assert load_zone_list_entries(zone_file)[-1].zones[-1] == "mirror"
    assert "desk" in load_zone_list_entries(zone_file)[-1].zones


def test_add_is_idempotent(zone_file: Path) -> None:
    _run("--set", "mirror")
    assert _run("--add", "mirror") == 0
    assert load_zone_list_entries(zone_file)[-1].zones == ("mirror",)


def test_add_dedupes_within_one_invocation(zone_file: Path) -> None:
    _run("--set", "desk")
    assert _run("--add", "mirror", "mirror") == 0
    assert load_zone_list_entries(zone_file)[-1].zones == ("desk", "mirror")


def test_remove_drops_a_zone(zone_file: Path) -> None:
    _run("--set", "desk", "mirror", "toilet")
    assert _run("--remove", "mirror") == 0
    assert load_zone_list_entries(zone_file)[-1].zones == ("desk", "toilet")


def test_remove_refuses_a_zone_that_is_not_there(
    zone_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A typo must not silently no-op and look like it worked."""
    _run("--set", "desk")
    capsys.readouterr()
    assert _run("--remove", "mirrr") == 1
    assert "not in the rotation: mirrr" in capsys.readouterr().out
    assert load_zone_list_entries(zone_file)[-1].zones == ("desk",)


def test_remove_refuses_to_empty_the_rotation(
    zone_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run("--set", "desk")
    capsys.readouterr()
    assert _run("--remove", "desk") == 1
    assert "at least one zone" in capsys.readouterr().out


def test_add_and_remove_compose_in_one_call(zone_file: Path) -> None:
    _run("--set", "desk", "entryway")
    assert _run("--add", "mirror", "--remove", "entryway") == 0
    assert load_zone_list_entries(zone_file)[-1].zones == ("desk", "mirror")
