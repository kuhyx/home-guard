"""Tests that both ConfigError and FirebaseAuthError become SyncUnavailableError."""

from __future__ import annotations

from crdt_sync import ConfigError, EncryptingStore, FirebaseAuthError
import pytest

import home_guard._sync_client as sync_client_module
from home_guard._sync_client import SyncUnavailableError, get_sync_client
from home_guard.tests.fake_remote_store import FakeRemoteStore


def test_config_error_becomes_sync_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_app_name: str) -> None:
        msg = "no config file"
        raise ConfigError(msg)

    monkeypatch.setattr(sync_client_module, "firebase_client_for", _raise)
    with pytest.raises(SyncUnavailableError, match="not configured"):
        get_sync_client()


def test_auth_error_becomes_sync_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_app_name: str) -> None:
        msg = "bad password"
        raise FirebaseAuthError(msg)

    monkeypatch.setattr(sync_client_module, "firebase_client_for", _raise)
    with pytest.raises(SyncUnavailableError, match="rejected"):
        get_sync_client()


def test_success_path_returns_encrypting_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = FakeRemoteStore()
    monkeypatch.setattr(sync_client_module, "firebase_client_for", lambda _app: inner)
    client = get_sync_client()
    assert isinstance(client, EncryptingStore)
    assert client is not inner
