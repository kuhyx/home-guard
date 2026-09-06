"""Wire gatelock's window/arbiter machinery into one running gate.

Mirrors ``leetcode_guard/_lock.py``'s construction order: build the config,
publish an arbiter claim, wait our turn behind any stronger incumbent, take
the holder lock, build the window, start the evidence poller, then grab
input. Implements gatelock's ``LockWindowHooks`` protocol directly.

Verified end-to-end by ``tests/test_lock_integration.py`` (construct, arm,
build a surface, close), run in an isolated Xvfb display and a fresh
subprocess. The coverage report still shows this module as mostly uncovered
because that test runs in a *subprocess* -- ``coverage.py`` cannot see
lines executed outside its own process without additional wiring this repo
does not have yet. Correctness is verified; the percentage is not accurate.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import tkinter as tk

from gatelock import (
    Arbiter,
    GateRoot,
    LockConfig,
    LockWindow,
    SurfaceInfo,
    wait_for_turn,
)

from home_guard._accept import AcceptResult, process_evidence
from home_guard._constants import RANK_HOME_GUARD
from home_guard._escape_hatch import SlotZone, build_tracker
from home_guard._network_incident import prepare_slot
from home_guard._paths import HomeGuardPaths
from home_guard._poller import EvidencePoller, PollerConfig
from home_guard._sync_evidence import fetch_evidence
from home_guard._view import EscapeDialogContext, build_surface, open_escape_dialog

_logger = logging.getLogger(__name__)

_APP_NAME = "home_guard"


class HomeGuardGuard:
    """One running instance of the home-guard lock."""

    def __init__(
        self,
        *,
        slot: str,
        demo_mode: bool = False,
        now: datetime | None = None,
        paths: HomeGuardPaths | None = None,
    ) -> None:
        """Build and arm the lock for ``slot``.

        Args:
            slot: The due slot key this instance is enforcing.
            demo_mode: Soft/closeable lock for manual testing, instead of
                the hard production lock.
            now: Injected clock, for tests.
            paths: Every overridable on-disk path/key-file, bundled. Tests
                always pass a ``tmp_path``-rooted instance so nothing here
                can touch real user state or the real shared arbiter
                runtime dir.
        """
        self._slot = slot
        self._demo_mode = demo_mode
        self._paths = paths if paths is not None else HomeGuardPaths()
        self._config = LockConfig(
            mode="hard",
            overrideredirect=True,
            grab="local" if demo_mode else "global",
            disable_vt=not demo_mode,
            app_name=_APP_NAME,
            rank=RANK_HOME_GUARD,
        )
        reference = now if now is not None else datetime.now(tz=UTC).astimezone()
        attempt = prepare_slot(reference, slot, paths=self._paths)
        self._zone = attempt.zone
        self._published = attempt.published

        self.root = GateRoot()
        self.root.on_callback_error = self._handle_callback_error
        self._zone_var = tk.StringVar(
            self.root, value=f"Clear the {self._zone} to unlock."
        )
        self._status_var = tk.StringVar(self.root, value=self._status_text())

        self._arbiter = Arbiter(
            _APP_NAME,
            RANK_HOME_GUARD,
            grab=self._config.resolved_grab(),
            disable_vt=self._config.resolved_disable_vt(),
        )
        self._arbiter.publish()
        wait_for_turn(self._arbiter)
        self._arbiter.acquire_holder()

        self._lock = LockWindow(
            self.root, self._config, hooks=self, arbiter=self._arbiter
        )
        self._lock.setup()
        self._tracker = build_tracker(
            path=self._paths.escape_history_path, key_file=self._paths.escape_key_file
        )
        self._poller = EvidencePoller(
            self.root,
            on_accept=self._on_accept,
            config=PollerConfig(on_reject=self._on_reject, check_fn=self._check_once),
        )
        self._poller.start()
        self._lock.grab_input()

    def _check_once(self) -> AcceptResult | None:
        payload = fetch_evidence()
        if payload is None:
            return None
        return process_evidence(payload, paths=self._paths)

    def _status_text(self) -> str:
        if self._published:
            return "Waiting for a photo from the home-guard app."
        return "Sync unavailable right now -- retrying, or use the escape hatch below."

    # -- LockWindowHooks protocol -----------------------------------------

    def build_surface(self, parent: tk.Misc, _surface: SurfaceInfo) -> None:
        """Build this app's widgets on one output."""
        build_surface(
            parent,
            self._config,
            zone_var=self._zone_var,
            status_var=self._status_var,
            on_report_trouble=self._open_escape_dialog,
        )

    def teardown_surface(self, _surface: SurfaceInfo) -> None:
        """Nothing per-surface to forget; all state is root-mastered."""

    def on_focus_ready(self, _surface: SurfaceInfo | None) -> None:
        """No initial input widget to focus."""

    def on_callback_error(self) -> None:
        """A Tk callback raised; close rather than leave a half-drawn lock."""
        self.close()

    def on_close(self) -> None:
        """Stop the poller before the window and grab are released."""
        self._poller.stop()

    # -- internal wiring ---------------------------------------------------

    def _handle_callback_error(self) -> None:
        self.on_callback_error()

    def _open_escape_dialog(self) -> None:
        open_escape_dialog(
            self.root,
            self._config,
            context=EscapeDialogContext(
                tracker=self._tracker,
                target=SlotZone(slot=self._slot, zone=self._zone),
                paths=self._paths,
            ),
            on_granted=self.close,
        )

    def _on_accept(self, _result: AcceptResult) -> None:
        _logger.info("home-guard slot %s verified; closing", self._slot)
        self.close()

    def _on_reject(self, reason: str) -> None:
        self._status_var.set(f"Last submission rejected: {reason}. Try again.")

    def close(self) -> None:
        """Release the lock and every hardware/input hold it took."""
        self._lock.close()

    def run(self) -> None:
        """Run the Tk mainloop; guaranteed cleanup on every exit path."""
        self._lock.run()
