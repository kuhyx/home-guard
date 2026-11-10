"""Guard for kuhy's textgate rule on the Tk lock: no painted word.

Builds the real lock (demo mode) in an isolated Xvfb display and a fresh
subprocess (see ``test_lock_integration.py`` for why a subprocess), opens
the escape dialog, triggers a rejection, and walks every widget. Each
painted string (``-text`` or the value behind ``-textvariable``) must hold
no run of two or more letters once the allowed content is removed: the
zone name (the user's own) and the bypass command (an escape phrase the
user types, kept by kuhy's settled decision).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import textwrap

from home_guard.tests.test_lock_integration import _site_packages

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = textwrap.dedent(
    """
    import json
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

    def painted(widget):
        out = []
        for child in widget.winfo_children():
            for option in ("textvariable", "text"):
                # Exact key check: Tk resolves cget("text") on an Entry to
                # its -textvariable by prefix, which would read a var name.
                if option not in child.keys():
                    continue
                value = str(child.cget(option))
                if option == "textvariable" and value:
                    value = str(child.getvar(value))
                if value:
                    out.append(value)
            out.extend(painted(child))
        return out

    def shoot():
        guard._open_escape_dialog()
        guard.root.update()
        print("LOCK=" + json.dumps(painted(guard.root)))
        guard._on_reject("token mismatch")
        guard.root.update()
        print("REJECT=" + json.dumps(painted(guard.root)))
        guard.close()

    guard.root.after(300, shoot)
    guard.run()
    print("CLOSED")
    """
)

_ALLOWED = ("desk", "systemctl --user stop home-guard-gate.service")
_WORD = re.compile(r"[A-Za-z]{2,}")


def _words(painted: list[str]) -> list[str]:
    hits = []
    for raw in painted:
        rest = raw
        for allowed in _ALLOWED:
            rest = rest.replace(allowed, "")
        if _WORD.search(rest):
            hits.append(raw)
    return hits


def test_lock_and_escape_dialog_paint_no_words(
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
    states = {
        line.split("=", 1)[0]: json.loads(line.split("=", 1)[1])
        for line in result.stdout.splitlines()
        if line.startswith(("LOCK=", "REJECT="))
    }
    assert set(states) == {"LOCK", "REJECT"}, result.stdout + result.stderr
    for name, painted in states.items():
        # An empty walk means nothing was built: that is red, not green.
        assert painted, name
        assert "desk" in painted, (name, painted)
        assert _words(painted) == [], (name, _words(painted))
