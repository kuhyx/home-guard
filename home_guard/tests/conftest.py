"""Shared fixtures: an isolated Xvfb display for the Tk lock-window tests.

Never uses the real ``:0`` display or the real ``$GATELOCK_RUNTIME_DIR`` --
a "hard" mode lock takes a global input grab, so running it against a real
session would actually lock the developer's screen and could queue behind
(or interfere with) their real running screen-locker/diet-guard/wake-alarm.
"""

from __future__ import annotations

import os
import select
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_XVFB_START_TIMEOUT_SECONDS = 5.0


@pytest.fixture(autouse=True)
def _isolate_free_days(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Never let the gate read the developer's real free-day pool.

    ``due_slots`` consults ``freedays.is_free_day()``, which defaults to
    ``~/.local/share/freedays/free_days.json``. Without this, marking a real
    free day would make every "the gate is due" test here fail -- and worse,
    it would fail for a reason that looks nothing like the cause.
    """
    import freedays._api

    # Deliberately not created: a missing pool reads as "no free days", and
    # creating it would leave a stray directory in every test's tmp_path --
    # which one test rightly asserts is empty.
    redirected = freedays.Paths.under(tmp_path / "freedays")
    monkeypatch.setattr(
        freedays._api, "resolve_paths", lambda paths: paths or redirected
    )


@pytest.fixture(autouse=True)
def _isolate_e2e_passphrase(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Never read the real ``~/.config/crdt-sync/password``; cheap Argon2.

    ``get_sync_client`` reads the shared passphrase and derives a key with
    Argon2id. A test reaching it without this would read kuhy's real secret.
    """
    from crdt_sync import Argon2Params, reset_e2e_copy_memo

    import home_guard._sync_client as sync_client_module

    reset_e2e_copy_memo()
    monkeypatch.setattr(sync_client_module, "_read_passphrase", lambda: "test-pass")
    # The derived-key cache would otherwise land in ~/.local/share/home_guard.
    monkeypatch.setattr(sync_client_module, "E2E_STATE_DIR", tmp_path / "e2e")
    monkeypatch.setattr(
        sync_client_module,
        "ARGON2_PARAMS",
        Argon2Params(memory_kib=8, iterations=1, parallelism=1),
    )


@pytest.fixture
def xvfb_display(tmp_path: Path) -> Iterator[dict[str, str]]:
    """Start an isolated Xvfb server; yield the env vars a Tk test needs.

    Skips (rather than fails) when Xvfb is not installed, so this suite
    stays runnable on a CI image without X11 tooling. Uses ``-displayfd``
    so Xvfb itself picks a free display number -- no scanning
    ``/tmp/.X11-unix`` and no race between checking and claiming one.
    """
    xvfb_path = shutil.which("Xvfb")
    if xvfb_path is None:
        pytest.skip("Xvfb is not installed")
    read_fd, write_fd = os.pipe()
    proc = subprocess.Popen(
        [
            xvfb_path,
            "-displayfd",
            str(write_fd),
            "-screen",
            "0",
            "640x480x24",
            "-nolisten",
            "tcp",
        ],
        pass_fds=(write_fd,),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.close(write_fd)
    try:
        ready, _, _ = select.select([read_fd], [], [], _XVFB_START_TIMEOUT_SECONDS)
        if not ready:
            pytest.skip("Xvfb did not report a display number in time")
        number = int(os.read(read_fd, 32).strip())
        env = {
            "DISPLAY": f":{number}",
            "GATELOCK_RUNTIME_DIR": str(tmp_path / "gatelock-runtime"),
        }
        yield env
    finally:
        os.close(read_fd)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def home_guard_state_dir(tmp_path: Path) -> Path:
    """A throwaway ``~/.local/share/home_guard``-shaped directory for Tk tests."""
    state_dir = tmp_path / "home_guard_state"
    state_dir.mkdir()
    return state_dir
