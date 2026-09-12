"""Tests for the disarm marker and the two CLI surfaces that honour it."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from home_guard._cli import build_parser
import home_guard._cli_gate as cli_gate_module
import home_guard._cli_status as cli_status_module
from home_guard._disarm import disarm_reason, is_disarmed

if TYPE_CHECKING:
    import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_is_disarmed_false_when_marker_absent(tmp_path: Path) -> None:
    assert is_disarmed(tmp_path / "DISARMED") is False


def test_is_disarmed_true_when_marker_present(tmp_path: Path) -> None:
    marker = tmp_path / "DISARMED"
    marker.write_text("rebuilding the app\n", encoding="utf-8")
    assert is_disarmed(marker) is True


def test_is_disarmed_false_when_marker_is_a_directory(tmp_path: Path) -> None:
    # is_file() must not be fooled by a directory of the same name, and must
    # fail in the "keep enforcing" direction rather than raising.
    marker = tmp_path / "DISARMED"
    marker.mkdir()
    assert is_disarmed(marker) is False


def test_disarm_reason_returns_marker_body(tmp_path: Path) -> None:
    marker = tmp_path / "DISARMED"
    marker.write_text("  rebuilding the phone app  \n", encoding="utf-8")
    assert disarm_reason(marker) == "rebuilding the phone app"


def test_disarm_reason_falls_back_when_empty(tmp_path: Path) -> None:
    marker = tmp_path / "DISARMED"
    marker.write_text("   \n", encoding="utf-8")
    assert disarm_reason(marker) == "no reason recorded"


def test_disarm_reason_falls_back_when_unreadable(tmp_path: Path) -> None:
    # A missing marker raises OSError from read_text; decorating a message
    # must never turn into a traceback.
    assert disarm_reason(tmp_path / "nope") == "no reason recorded"


def test_disarm_defaults_to_the_real_marker_path() -> None:
    # Exercises the `marker_path is None` branch without creating anything:
    # the real path does not exist in CI, so this must simply be False.
    from home_guard._constants import DISARM_MARKER_FILE

    assert is_disarmed() == DISARM_MARKER_FILE.is_file()


def test_cmd_gate_refuses_while_disarmed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate must return 0 and never reach due_slots or the lock."""
    calls: list[str] = []
    # Patched in the CONSUMING module: `from ... import is_disarmed` bound a
    # new name in _cli_gate, so patching _disarm would do nothing here.
    monkeypatch.setattr(cli_gate_module, "is_disarmed", lambda: True)
    monkeypatch.setattr(cli_gate_module, "disarm_reason", lambda: "under rebuild")
    monkeypatch.setattr(
        cli_gate_module, "due_slots", lambda *a, **k: calls.append("due") or ()
    )

    args = build_parser().parse_args(["gate"])
    assert cli_gate_module.cmd_gate(args) == 0
    assert calls == [], "due_slots must not run while disarmed"
    out = capsys.readouterr().out
    assert "disarmed" in out
    assert "under rebuild" in out


def test_cmd_status_announces_disarmed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Status shouts about it, then still reports the real state."""
    monkeypatch.setattr(cli_status_module, "is_disarmed", lambda: True)
    monkeypatch.setattr(cli_status_module, "disarm_reason", lambda: "under rebuild")
    monkeypatch.setattr(cli_status_module, "due_slots", lambda *a, **k: ())
    monkeypatch.setattr(cli_status_module, "gate_message", lambda *a, **k: "zone msg")

    args = build_parser().parse_args(["status"])
    assert cli_status_module.cmd_status(args) == 0
    out = capsys.readouterr().out
    assert "ENFORCEMENT DISARMED" in out
    assert "under rebuild" in out
    # The real state still gets printed -- "what would be due if I re-armed"
    # stays a useful question while disarmed.
    assert "zone msg" in out


def test_bash_and_python_markers_cannot_drift() -> None:
    """The shell half and the Python half must name the same file.

    A disable that half-works -- systemd stopped but `install.sh` still
    willing, or vice versa -- is the exact failure this pair exists to
    prevent, and it would be invisible until the day it mattered.
    """
    from home_guard._constants import DISARM_MARKER_FILE

    guard = (_REPO_ROOT / "scripts" / "disarm_guard.sh").read_text(encoding="utf-8")
    suffix = f"{DISARM_MARKER_FILE.parent.name}/{DISARM_MARKER_FILE.name}"
    assert suffix in guard, f"{suffix} not found in scripts/disarm_guard.sh"


def test_install_sh_refuses_before_arming() -> None:
    """`refuse_if_disarmed` must guard both main() and install_units()."""
    install_sh = (_REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    assert install_sh.count("refuse_if_disarmed") >= 2
    assert 'source "$REPO_DIR/scripts/disarm_guard.sh"' in install_sh


def test_cmd_gate_reports_nothing_due_when_armed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The armed-but-idle path, pinned so it cannot depend on the real marker."""
    monkeypatch.setattr(cli_gate_module, "is_disarmed", lambda: False)
    monkeypatch.setattr(cli_gate_module, "due_slots", lambda _now: ())
    args = build_parser().parse_args(["gate"])
    assert cli_gate_module.cmd_gate(args) == 0
    assert "nothing due" in capsys.readouterr().out
