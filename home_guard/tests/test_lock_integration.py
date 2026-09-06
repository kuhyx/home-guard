"""End-to-end Tk integration test: does the real lock render and close?

Runs the guard in a **subprocess** with HOME redirected, not in-process --
several modules (``crdt_sync``'s config path among them) resolve
``Path.home()`` into module-level constants at import time, so patching the
environment after those modules are already imported would not isolate
anything. A fresh subprocess with HOME set before its first import is the
only way to guarantee this test cannot reach real Firebase credentials or
write into the real ``~/.local/share/home_guard``.

Also runs against an isolated Xvfb display and ``GATELOCK_RUNTIME_DIR`` (see
``conftest.py``), so it never touches the developer's real screen or the
real shared arbiter state used by their actually-running sibling gates.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = textwrap.dedent(
    """
    from datetime import UTC, datetime
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
    print("ZONE=" + guard._zone)
    print("EXISTS=" + str(bool(guard.root.winfo_exists())))
    guard.root.after(300, guard.close)
    guard.run()
    print("CLOSED")
    """
)


def test_guard_constructs_arms_and_closes_cleanly(
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
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ZONE=desk" in result.stdout
    assert "EXISTS=True" in result.stdout
    assert "CLOSED" in result.stdout
    # Nothing here should have needed root or a real Firebase credential.
    assert (work_dir / "challenges.json").is_file()


def _site_packages() -> str:
    import site

    for candidate in (*site.getsitepackages(), site.getusersitepackages()):
        if (Path(candidate) / "gatelock").is_dir():
            return candidate
    pytest.skip("gatelock not importable from any known site-packages dir")
