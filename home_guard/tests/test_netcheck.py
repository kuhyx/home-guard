"""Tests for reachability classification, with injected probes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from home_guard._netcheck import classify_reachability

if TYPE_CHECKING:
    import pytest


def test_ok_when_firebase_reachable() -> None:
    result = classify_reachability(
        check_general_internet=lambda: True, check_firebase=lambda: True
    )
    assert result == "ok"


def test_remote_unreachable_when_only_general_internet_up() -> None:
    result = classify_reachability(
        check_general_internet=lambda: True, check_firebase=lambda: False
    )
    assert result == "remote_unreachable"


def test_local_unreachable_when_nothing_up() -> None:
    result = classify_reachability(
        check_general_internet=lambda: False, check_firebase=lambda: False
    )
    assert result == "local_unreachable"


def test_real_probe_path_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    # Exercises the non-injected default lambdas without touching the
    # network: patch socket.create_connection itself.
    import socket

    def _fail(*_args: object, **_kwargs: object) -> None:
        msg = "no route"
        raise OSError(msg)

    monkeypatch.setattr(socket, "create_connection", _fail)
    assert classify_reachability(timeout=0.01) == "local_unreachable"


def test_real_probe_path_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import contextlib
    import socket

    monkeypatch.setattr(
        socket, "create_connection", lambda *_a, **_k: contextlib.nullcontext()
    )
    assert classify_reachability(timeout=0.01) == "ok"
