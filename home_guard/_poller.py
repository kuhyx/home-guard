"""Poll Firebase for evidence off the Tk thread; accept it if it verifies.

Mirrors leetcode-guard's ``SolvePoller`` shape: the network/disk check runs
on a single-worker ``ThreadPoolExecutor`` so it can never block the Tk event
loop, the result is drained back onto the Tk thread on a short timer, and no
exception raised inside the check is allowed to kill the polling loop.

Depends on ``root`` only through the two methods every Tk widget/root
exposes (``after``/``after_cancel``), so tests can drive it with a plain
fake instead of a real display.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import contextlib
from dataclasses import dataclass
import logging
import tkinter as tk
from typing import TYPE_CHECKING, Protocol

from home_guard._accept import AcceptResult, process_evidence
from home_guard._constants import POLL_DRAIN_MS, POLL_INTERVAL_MS
from home_guard._sync_evidence import fetch_evidence

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)

# The exception surface a single check can plausibly raise: disk IO
# (OSError), malformed data slipping past the defensive `.get()` calls
# upstream (TypeError/KeyError/ValueError). Deliberately not a bare
# `Exception`/`BaseException` catch -- narrow enough to stay meaningful,
# wide enough that a bad tick can never kill the polling loop.
_CHECK_EXCEPTIONS = (OSError, TypeError, KeyError, ValueError)


class _TkSchedulable(Protocol):
    """The two methods this module needs from a Tk root or widget."""

    def after(self, ms: int, func: Callable[[], None]) -> str: ...
    def after_cancel(self, identifier: str) -> None: ...


@dataclass(frozen=True)
class PollerConfig:
    """Tuning knobs and test-injection seams for one :class:`EvidencePoller`.

    Bundled together because they are all optional overrides of the same
    kind -- how often it ticks, and what it runs instead of the real
    Firebase/disk check -- as opposed to ``root``/``on_accept``, which are
    load-bearing on every construction.
    """

    on_reject: Callable[[str], None] | None = None
    poll_interval_ms: int = POLL_INTERVAL_MS
    drain_interval_ms: int = POLL_DRAIN_MS
    executor: ThreadPoolExecutor | None = None
    check_fn: Callable[[], AcceptResult | None] | None = None


class EvidencePoller:
    """Periodically checks for uploaded evidence and accepts a valid match."""

    def __init__(
        self,
        root: _TkSchedulable,
        *,
        on_accept: Callable[[AcceptResult], None],
        config: PollerConfig | None = None,
    ) -> None:
        """Bind a poller to ``root``'s event loop.

        Args:
            root: Anything exposing ``after``/``after_cancel`` (a real Tk
                root, or a fake for tests).
            on_accept: Called with the accepted result; the caller is
                expected to close the lock. Polling stops once this fires.
            config: Bundled optional overrides -- rejection callback, tick
                intervals, injected executor/check function. See
                :class:`PollerConfig`.
        """
        resolved = config if config is not None else PollerConfig()
        self._root = root
        self._on_accept = on_accept
        self._on_reject = resolved.on_reject
        self._check_fn = (
            resolved.check_fn if resolved.check_fn is not None else self._default_check
        )
        self._poll_interval_ms = resolved.poll_interval_ms
        self._drain_interval_ms = resolved.drain_interval_ms
        self._executor = (
            resolved.executor
            if resolved.executor is not None
            else ThreadPoolExecutor(max_workers=1, thread_name_prefix="home-guard-poll")
        )
        self._future: Future[AcceptResult | None] | None = None
        self._stopped = False
        self._after_id: str | None = None

    def start(self) -> None:
        """Schedule the first tick."""
        self._schedule_tick()

    def stop(self) -> None:
        """Cancel any pending tick and shut down the worker thread.

        Idempotent, and safe to call even if never started.
        """
        self._stopped = True
        if self._after_id is not None:
            with contextlib.suppress(tk.TclError):
                self._root.after_cancel(self._after_id)
            self._after_id = None
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _schedule_tick(self) -> None:
        if self._stopped:
            return
        self._after_id = self._root.after(self._poll_interval_ms, self._tick)

    def _tick(self) -> None:
        if self._stopped:
            return
        if self._future is None:
            self._future = self._executor.submit(self._check_once)
        self._drain()

    def _drain(self) -> None:
        if self._stopped:
            return
        future = self._future
        if future is not None and future.done():
            self._future = None
            result = self._guarded_result(future)
            if result is not None and result.accepted:
                self._on_accept(result)
                return  # the caller closes the lock; stop polling here.
            if result is not None and result.reason is not None and self._on_reject:
                self._on_reject(result.reason)
            self._schedule_tick()
            return
        self._after_id = self._root.after(self._drain_interval_ms, self._drain)

    def _guarded_result(
        self, future: Future[AcceptResult | None]
    ) -> AcceptResult | None:
        try:
            return future.result()
        except _CHECK_EXCEPTIONS:
            _logger.exception("home-guard evidence check raised")
            return None

    def _check_once(self) -> AcceptResult | None:
        return self._check_fn()

    @staticmethod
    def _default_check() -> AcceptResult | None:
        payload = fetch_evidence()
        if payload is None:
            return None
        return process_evidence(payload)
