"""Tests for fetching, draining, and persisting evidence photos."""

from __future__ import annotations

import json

from home_guard._constants import SYNC_EVIDENCE_PATH
from home_guard._sync_evidence import (
    drain_evidence,
    fetch_evidence,
)
from home_guard.tests.fake_remote_store import FakeRemoteStore


def test_fetch_returns_none_when_empty() -> None:
    client = FakeRemoteStore()
    assert fetch_evidence(client=client) is None


def test_fetch_returns_none_when_drained_payload() -> None:
    client = FakeRemoteStore()
    client.put_file_text(SYNC_EVIDENCE_PATH, "{}", message="")
    assert fetch_evidence(client=client) is None


def test_fetch_returns_none_on_corrupt_json() -> None:
    client = FakeRemoteStore()
    client.put_file_text(SYNC_EVIDENCE_PATH, "not json", message="")
    assert fetch_evidence(client=client) is None


def test_fetch_returns_none_on_outage() -> None:
    client = FakeRemoteStore(fail=True)
    assert fetch_evidence(client=client) is None


def test_fetch_returns_payload_when_present() -> None:
    client = FakeRemoteStore()
    client.put_file_text(
        SYNC_EVIDENCE_PATH, json.dumps({"day": "2026-09-06"}), message=""
    )
    assert fetch_evidence(client=client) == {"day": "2026-09-06"}


def test_drain_writes_empty_object() -> None:
    client = FakeRemoteStore()
    client.put_file_text(SYNC_EVIDENCE_PATH, json.dumps({"x": 1}), message="")
    assert drain_evidence(client=client) is True
    assert fetch_evidence(client=client) is None


def test_drain_returns_false_on_outage() -> None:
    client = FakeRemoteStore(fail=True)
    assert drain_evidence(client=client) is False


def test_fake_remote_store_list_and_delete_and_probe() -> None:
    client = FakeRemoteStore()
    client.put_file_text("dir/a.json", "1", message="")
    client.put_file_text("dir/b.json", "2", message="")
    assert sorted(client.list_directory("dir")) == ["a.json", "b.json"]
    assert client.can_access_remote() is True
    client.delete_file("dir/a.json")
    assert client.get_file_text("dir/a.json") is None
    client.close()


def test_fake_remote_store_fail_mode_raises_on_every_method() -> None:
    from crdt_sync import RemoteSyncError
    import pytest

    client = FakeRemoteStore(fail=True)
    assert client.can_access_remote() is False
    with pytest.raises(RemoteSyncError):
        client.list_directory("dir")
    with pytest.raises(RemoteSyncError):
        client.delete_file("dir/a.json")
