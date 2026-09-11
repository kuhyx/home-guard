"""Tests for the uiautomator-dump reader behind register_oauth_client.sh."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from home_guard._ui_dump import find_centre, has_text, main

if TYPE_CHECKING:
    from pathlib import Path

_DUMP = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy rotation="0">
  <node index="0" text="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
    <node index="1" text="Not connected" content-desc="" bounds="[100,900][980,1000]" />
    <node index="2" text="" content-desc="Settings" bounds="[960,140][1040,220]" />
    <node index="3" text="No bounds here" bounds="garbage" />
  </node>
</hierarchy>
"""


def test_find_centre_reads_the_first_match_case_insensitively() -> None:
    assert find_centre(_DUMP, "not CONNECTED") == (540, 950)


def test_find_centre_matches_content_desc_too() -> None:
    assert find_centre(_DUMP, "settings") == (1000, 180)


def test_find_centre_skips_unparseable_bounds_and_misses() -> None:
    assert find_centre(_DUMP, "no bounds") is None
    assert find_centre(_DUMP, "absent") is None


def test_has_text() -> None:
    assert has_text(_DUMP, "Not connected")
    assert not has_text(_DUMP, "Nothing due")


@pytest.fixture
def dump_file(tmp_path: Path) -> Path:
    path = tmp_path / "ui.xml"
    path.write_text(_DUMP, encoding="utf-8")
    return path


def test_main_has_exit_codes(dump_file: Path) -> None:
    assert main([str(dump_file), "has", "Not connected"]) == 0
    assert main([str(dump_file), "has", "zzz"]) == 1


def test_main_centre_prints_coordinates(
    dump_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(dump_file), "centre", "Settings"]) == 0
    assert capsys.readouterr().out == "1000 180\n"
    assert main([str(dump_file), "centre", "zzz"]) == 1


def test_main_usage_and_missing_dump(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["only-one"]) == 2
    assert "Usage" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.xml"), "has", "x"]) == 2
    assert "no such dump" in capsys.readouterr().err


def test_main_defaults_to_sys_argv(
    dump_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sys.argv", ["_ui_dump", str(dump_file), "has", "Not connected"]
    )
    assert main() == 0


def test_module_entrypoint_exits_with_main_status(
    dump_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import runpy

    monkeypatch.setattr("sys.argv", ["_ui_dump", str(dump_file), "has", "zzz"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("home_guard._ui_dump", run_name="__main__")
    assert exc.value.code == 1
