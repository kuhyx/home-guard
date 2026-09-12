"""Tests for the evidence poller's scheduling state machine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time
from typing import TYPE_CHECKING

from home_guard._accept import AcceptResult
import home_guard._poller as poller_module
from home_guard._poller import EvidencePoller, PollerConfig
from home_guard.tests.fake_tk_root import FakeTkRoot, ImmediateExecutor

if TYPE_CHECKING:
    import pytest

_ACCEPTED = AcceptResult(accepted=True, reason=None)
_REJECTED = AcceptResult(accepted=False, reason="token_mismatch")


def test_poller_accepts_and_stops_scheduling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(poller_module, "fetch_evidence", lambda: {"day": "x"})
    monkeypatch.setattr(poller_module, "process_evidence", lambda _payload: _ACCEPTED)
    root = FakeTkRoot()
    accepted: list[AcceptResult] = []
    poller = EvidencePoller(
        root,
        on_accept=accepted.append,
        config=PollerConfig(executor=ImmediateExecutor()),
    )
    poller.start()
    root.run_until_idle()
    assert accepted == [_ACCEPTED]
    # Once accepted, nothing further is scheduled -- the caller closes the lock.
    assert root.pending_count == 0


def test_poller_reports_rejection_and_keeps_polling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(poller_module, "fetch_evidence", lambda: {"day": "x"})
    monkeypatch.setattr(poller_module, "process_evidence", lambda _payload: _REJECTED)
    root = FakeTkRoot()
    rejections: list[str] = []
    poller = EvidencePoller(
        root,
        on_accept=lambda _r: None,
        config=PollerConfig(on_reject=rejections.append, executor=ImmediateExecutor()),
    )
    poller.start()
    # With a synchronous executor, each _tick call completes and reports its
    # own rejection immediately, then reschedules the next tick.
    for _ in range(3):
        root.run_next()
    assert rejections == ["token_mismatch", "token_mismatch", "token_mismatch"]


def test_poller_no_evidence_yet_reschedules_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(poller_module, "fetch_evidence", lambda: None)
    root = FakeTkRoot()
    poller = EvidencePoller(
        root,
        on_accept=lambda _r: None,
        config=PollerConfig(executor=ImmediateExecutor()),
    )
    poller.start()
    for _ in range(4):
        root.run_next()
    assert root.pending_count == 1  # still waiting on the next tick


def test_poller_stop_cancels_pending_and_is_idempotent() -> None:
    root = FakeTkRoot()
    poller = EvidencePoller(
        root,
        on_accept=lambda _r: None,
        config=PollerConfig(executor=ImmediateExecutor()),
    )
    poller.start()
    assert root.pending_count == 1
    poller.stop()
    assert root.pending_count == 0
    poller.stop()  # idempotent, no error


def test_poller_drain_waits_when_future_not_done() -> None:
    root = FakeTkRoot()
    real_executor = ThreadPoolExecutor(max_workers=1)

    started = []

    def _slow_check() -> None:
        started.append(True)
        time.sleep(0.05)

    poller = EvidencePoller(
        root,
        on_accept=lambda _r: None,
        config=PollerConfig(executor=real_executor, check_fn=_slow_check),
    )
    poller.start()
    root.run_next()  # _tick: submits the slow job, then calls _drain (not done yet)
    assert root.pending_count == 1  # _drain rescheduled itself
    time.sleep(0.1)
    root.run_next()  # this _drain call should now see it as done
    real_executor.shutdown(wait=True)
    assert started == [True]


def test_stopped_poller_ignores_a_late_tick_and_drain() -> None:
    # A callback already queued before stop() can still fire afterward; every
    # entry point must no-op rather than reschedule once stopped.
    root = FakeTkRoot()
    poller = EvidencePoller(
        root,
        on_accept=lambda _r: None,
        config=PollerConfig(executor=ImmediateExecutor()),
    )
    poller.start()
    poller.stop()
    poller._schedule_tick()
    poller._tick()
    poller._drain()
    assert root.pending_count == 0


def test_guarded_result_survives_worker_exception() -> None:
    root = FakeTkRoot()
    real_executor = ThreadPoolExecutor(max_workers=1)
    accepted: list[AcceptResult] = []

    def _boom() -> None:
        msg = "disk full"
        raise OSError(msg)

    poller = EvidencePoller(
        root,
        on_accept=accepted.append,
        config=PollerConfig(executor=real_executor, check_fn=_boom),
    )
    poller.start()
    root.run_next()
    time.sleep(0.05)
    root.run_until_idle()
    real_executor.shutdown(wait=True)
    assert accepted == []
