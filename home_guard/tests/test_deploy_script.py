"""scripts/deploy.sh against a scratch origin, never kuhy's real checkout.

The live checkout, the system python and systemctl are all stand-ins under
tmp_path: the python and systemctl stubs answer exactly the questions the
script asks, so nothing here can touch the real editable install, the real
units or ~/src/home-guard.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEPLOY = _REPO_ROOT / "scripts" / "deploy.sh"

_PYTHON_STUB = """#!/bin/bash
case "$*" in
    *'print(home_guard.__file__)'*)
        echo "$HOME_GUARD_LIVE_REPO/home_guard/__init__.py" ;;
    *'-m home_guard status'*) echo 'due slots today: 0800' ;;
esac
"""
_SYSTEMCTL_STUB = "#!/bin/bash\necho masked\n"


def _tool(name: str) -> str:
    """Absolute path of a host tool (ruff S607: no partial executable paths)."""
    path = shutil.which(name)
    assert path is not None, f"{name} not on PATH"
    return path


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        [_tool("git"), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _stub(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _lagging_clone(tmp_path: Path) -> tuple[Path, str]:
    """Return a clone one commit behind its origin, and the origin's head."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", str(origin), str(seed))
    for name in ("one", "two"):
        (seed / name).write_text(name, encoding="utf-8")
        _git(seed, "add", name)
        _git(seed, "commit", "-q", "--no-verify", "-m", name)
    _git(seed, "push", "-q", "origin", "HEAD:main")
    live = tmp_path / "live"
    _git(tmp_path, "clone", "-q", str(origin), str(live))
    _git(live, "reset", "-q", "--hard", "HEAD~1")
    return live, _git(seed, "rev-parse", "HEAD")


def _run_deploy(tmp_path: Path, live: Path) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir / "systemctl", _SYSTEMCTL_STUB)
    marker = tmp_path / "DISARMED"
    marker.write_text("test\n", encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME_GUARD_LIVE_REPO": str(live),
        "DEPLOY_PYTHON": str(_stub(tmp_path / "python3", _PYTHON_STUB)),
        "DISARM_MARKER": str(marker),
    }
    return subprocess.run(
        [_tool("bash"), str(_DEPLOY), "--desktop-only"],
        env=env,
        capture_output=True,
        text=True,
        timeout=50,
        check=False,
    )


def test_deploy_fast_forwards_a_lagging_live_checkout(tmp_path: Path) -> None:
    live, newest = _lagging_clone(tmp_path)
    assert _git(live, "rev-parse", "HEAD") != newest

    done = _run_deploy(tmp_path, live)

    assert done.returncode == 0, done.stderr
    assert _git(live, "rev-parse", "HEAD") == newest
    assert "due slots today: 0800" in done.stderr


def test_deploy_fails_named_when_the_pull_cannot_fast_forward(tmp_path: Path) -> None:
    live, _ = _lagging_clone(tmp_path)
    # A local file the incoming commit would overwrite: git refuses the pull.
    (live / "two").write_text("local edit", encoding="utf-8")

    done = _run_deploy(tmp_path, live)

    assert done.returncode != 0
    assert "FAILED [pull]" in done.stderr
