"""Tests for fetching, draining, and persisting evidence photos."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

from home_guard._constants import SYNC_EVIDENCE_PATH
from home_guard._sync_evidence import (
    drain_evidence,
    fetch_evidence,
    save_evidence_photo,
)
from home_guard.tests.fake_remote_store import FakeRemoteStore

if TYPE_CHECKING:
    from pathlib import Path


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


def test_save_evidence_photo_writes_decoded_bytes(tmp_path: Path) -> None:
    raw = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "Kitchen Counter!",
        "photo_b64": base64.b64encode(raw).decode("ascii"),
    }
    target = save_evidence_photo(payload, photos_dir=tmp_path)
    assert target is not None
    assert target.read_bytes() == raw
    assert target.name == "2026-09-06-0800-kitchen-counter.jpg"


def test_save_evidence_photo_none_on_missing_field(tmp_path: Path) -> None:
    assert save_evidence_photo({"day": "2026-09-06"}, photos_dir=tmp_path) is None


def test_save_evidence_photo_none_when_over_size_cap(tmp_path: Path) -> None:
    from home_guard._constants import MAX_EVIDENCE_PHOTO_BYTES

    oversized = b"\x00" * (MAX_EVIDENCE_PHOTO_BYTES + 1)
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "photo_b64": base64.b64encode(oversized).decode("ascii"),
    }
    assert save_evidence_photo(payload, photos_dir=tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_save_evidence_photo_none_on_bad_base64(tmp_path: Path) -> None:
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "photo_b64": "not-valid-base64!!",
    }
    assert save_evidence_photo(payload, photos_dir=tmp_path) is None


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
