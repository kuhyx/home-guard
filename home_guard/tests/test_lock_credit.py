"""The real Tk lock shows kuhy's shared credit logo (``kuhy_credit.tk``).

Same isolation as ``test_lock_integration.py``: a fresh subprocess with HOME
redirected, an Xvfb display and a private ``GATELOCK_RUNTIME_DIR``. The
script finds the ``KuhyCredit`` widget on the lock, clicks it (the panel
opens), clicks the panel (the stubbed opener gets the credit URL) and checks
the panel closed again.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap

from home_guard.tests.test_lock_integration import _site_packages

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = textwrap.dedent(
    """
    from datetime import UTC, datetime
    from kuhy_credit import URL
    from kuhy_credit.tk import KuhyCredit
    from home_guard._lock import HomeGuardGuard
    from home_guard._paths import HomeGuardPaths
    from home_guard._zone_list import record_zone_list_change

    paths = HomeGuardPaths(
        challenge_path=Path("challenges.json"),
        challenge_key_file=Path("no-key"),
        log_path=Path("clear_log.json"),
        log_key_file=Path("no-key"),
        photos_dir=Path("photos"),
        zone_cursor_path=Path(".zone_cursor"),
        zone_list_path=Path(".zone_list"),
        escape_history_path=Path("escape_history.json"),
        escape_key_file=Path("no-key"),
    )
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=paths.zone_list_path
    )
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    guard = HomeGuardGuard(slot="0800", demo_mode=True, now=now, paths=paths)

    def credits(widget):
        found = [widget] if isinstance(widget, KuhyCredit) else []
        for child in widget.winfo_children():
            found.extend(credits(child))
        return found

    def check():
        found = credits(guard.root)
        print("CREDITS=" + str(len(found)))
        if found:
            credit = found[0]
            opened = []
            credit._open_url = opened.append
            guard.root.update()
            print("MAPPED=" + str(bool(credit.winfo_ismapped())))
            credit.event_generate("<Button-1>")
            guard.root.update()
            print("OPEN=" + str(credit.is_open))
            credit.panel.event_generate("<Button-1>")
            guard.root.update()
            print("URL_OK=" + str(opened == [URL]))
            print("CLOSED_PANEL=" + str(not credit.is_open))
        guard.close()

    guard.root.after(300, check)
    guard.run()
    print("CLOSED")
    """
)


def test_lock_shows_clickable_credit_logo(
    xvfb_display: dict[str, str], tmp_path: Path
) -> None:
    script = tmp_path / "run_guard.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(_REPO_ROOT)!r})\n" + _SCRIPT,
        encoding="utf-8",
    )
    work_dir = tmp_path / "workdir"
    work_dir.mkdir()
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(fake_home),
        "PYTHONPATH": _site_packages(),
        **xvfb_display,
    }
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=work_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "CREDITS=1" in result.stdout, out
    assert "MAPPED=True" in result.stdout, out
    assert "OPEN=True" in result.stdout, out
    assert "URL_OK=True" in result.stdout, out
    assert "CLOSED_PANEL=True" in result.stdout, out
    assert "CLOSED" in result.stdout, out
