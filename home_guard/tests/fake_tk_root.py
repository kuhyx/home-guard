"""Fakes standing in for a Tk root's scheduling API and a thread pool.

Neither touches a real display or a real thread, so ``_poller.py``'s state
machine can be driven deterministically, one step at a time.
"""

from __future__ import annotations

from concurrent.futures import Future
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class FakeTkRoot:
    """A queue of pending ``after`` callbacks, drained one at a time."""

    def __init__(self) -> None:
        self._scheduled: list[tuple[str, Callable[[], None]]] = []
        self._next_id = 0

    def after(self, _ms: int, func: Callable[[], None]) -> str:
        self._next_id += 1
        ident = str(self._next_id)
        self._scheduled.append((ident, func))
        return ident

    def after_cancel(self, identifier: str) -> None:
        self._scheduled = [
            (ident, func) for ident, func in self._scheduled if ident != identifier
        ]

    def run_next(self) -> bool:
        """Run the oldest pending callback. Returns False if none is queued."""
        if not self._scheduled:
            return False
        _, func = self._scheduled.pop(0)
        func()
        return True

    def run_until_idle(self, *, max_steps: int = 100) -> int:
        """Run pending callbacks until none remain. Returns the step count."""
        steps = 0
        while steps < max_steps and self.run_next():
            steps += 1
        return steps

    @property
    def pending_count(self) -> int:
        return len(self._scheduled)


class ImmediateExecutor:
    """A ThreadPoolExecutor stand-in that runs the job synchronously.

    Only used with callables that do not raise -- tests exercising the
    "worker raised" path use a real ``ThreadPoolExecutor`` instead, so the
    exception genuinely propagates through a future the way it would in
    production, rather than this fake having to reimplement that capture.
    """

    def submit(self, fn: Callable[[], object]) -> Future:
        future: Future = Future()
        future.set_result(fn())
        return future

    def shutdown(self, *, wait: bool = True, cancel_futures: bool = False) -> None:
        return None
