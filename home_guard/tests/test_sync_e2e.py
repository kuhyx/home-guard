"""End-to-end encryption of every home-guard RTDB payload.

Drives the real :func:`get_sync_client` over an in-memory store, with the
passphrase injected (never the real ``~/.config/crdt-sync/password``) and a
cheap Argon2 cost so the suite stays fast.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crdt_sync import E2eLayout, reset_e2e_copy_memo
import pytest

from home_guard._challenge_store import ChallengeRecord
from home_guard._constants import (
    SYNC_CHALLENGE_PATH,
    SYNC_EVIDENCE_PATH,
    SYNC_OLD_PREFIX,
    SYNC_PREFIX,
    SYNC_ZONES_PATH,
)
from home_guard._sync_challenge import publish_challenge
import home_guard._sync_client as sync_client_module
from home_guard._sync_client import (
    SyncLockedError,
    SyncUnavailableError,
    _read_passphrase,
    get_sync_client,
)
from home_guard._sync_evidence import drain_evidence, fetch_evidence
from home_guard._sync_zones import fetch_zone_history, publish_zone_history
from home_guard._zone_list import ZoneListEntry
from home_guard.tests.fake_remote_store import FakeRemoteStore

if TYPE_CHECKING:
    from pathlib import Path

_SEALED_VALUE = "secret-token-123"
_RECORD = ChallengeRecord(
    day="2026-11-12",
    slot="2026-11-12T08:00",
    zone="mirror",
    token=_SEALED_VALUE,
    issued_at="2026-11-12T08:00:00+00:00",
    consumed=False,
)
_ENTRIES = (
    ZoneListEntry(
        effective_from="2026-11-12",
        zones=("mirror", "toilet"),
        edited_at="2026-11-12T19:00:00+00:00",
    ),
)


@pytest.fixture
def remote(monkeypatch: pytest.MonkeyPatch) -> FakeRemoteStore:
    """A fake RTDB behind the real client factory.

    conftest's autouse fixture already injects the passphrase and cheap Argon2.
    """
    store = FakeRemoteStore()
    monkeypatch.setattr(sync_client_module, "firebase_client_for", lambda _app: store)
    return store


def test_paths_live_under_the_e2e_layout_of_the_old_prefix() -> None:
    assert SYNC_OLD_PREFIX == "home-guard-sync"
    assert E2eLayout.of(SYNC_OLD_PREFIX).prefix == SYNC_PREFIX == "home-guard-sync-e2e"
    for path in (SYNC_CHALLENGE_PATH, SYNC_EVIDENCE_PATH, SYNC_ZONES_PATH):
        assert path.startswith(f"{SYNC_PREFIX}/")


def test_challenge_is_sealed_on_the_wire(remote: FakeRemoteStore) -> None:
    assert publish_challenge(_RECORD) is True
    raw = remote.get_file_text(SYNC_CHALLENGE_PATH)
    assert raw is not None
    assert "secret-token-123" not in raw
    assert '"token"' not in raw
    assert "mirror" not in raw
    # Nothing landed under the old plaintext prefix.
    assert not [p for p in remote._files if p.startswith(f"{SYNC_OLD_PREFIX}/")]


def test_zones_round_trip_sealed(remote: FakeRemoteStore) -> None:
    assert publish_zone_history(_ENTRIES) is True
    raw = remote.get_file_text(SYNC_ZONES_PATH)
    assert raw is not None
    assert "toilet" not in raw
    assert fetch_zone_history() == _ENTRIES


def test_evidence_written_by_a_peer_opens_and_drains_sealed(
    remote: FakeRemoteStore,
) -> None:
    peer = get_sync_client()
    peer.put_file_text(
        SYNC_EVIDENCE_PATH, '{"token": "secret-token-123"}', message="phone"
    )
    assert "secret-token-123" not in (remote.get_file_text(SYNC_EVIDENCE_PATH) or "")
    assert fetch_evidence() == {"token": "secret-token-123"}
    assert drain_evidence() is True
    assert fetch_evidence() is None
    assert remote.get_file_text(SYNC_EVIDENCE_PATH) != "{}"


def test_no_passphrase_is_locked_and_writes_nothing(
    remote: FakeRemoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sync_client_module, "_read_passphrase", lambda: "")
    with pytest.raises(SyncLockedError):
        get_sync_client()
    assert issubclass(SyncLockedError, SyncUnavailableError)
    assert publish_challenge(_RECORD) is False
    assert publish_zone_history(_ENTRIES) is False
    assert drain_evidence() is False
    assert remote._files == {}


def test_wrong_passphrase_is_locked_and_writes_nothing_more(
    remote: FakeRemoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert publish_zone_history(_ENTRIES) is True
    before = dict(remote._files)
    monkeypatch.setattr(sync_client_module, "_read_passphrase", lambda: "wrong")
    assert publish_challenge(_RECORD) is False
    assert fetch_zone_history() is None
    assert remote._files == before


# The autouse fixture replaces the module attribute; ``_read_passphrase`` here
# is the original, bound at import, pointed at a tmp file instead.
def test_read_passphrase_strips_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = tmp_path / "password"
    secret.write_text("hunter2\n", encoding="utf-8")
    monkeypatch.setattr(sync_client_module, "PASSWORD_FILE", secret)
    assert _read_passphrase() == "hunter2"


def test_read_passphrase_missing_file_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sync_client_module, "PASSWORD_FILE", tmp_path / "absent")
    assert _read_passphrase() == ""


def test_restart_with_legacy_drained_evidence_keeps_pending_upload(
    remote: FakeRemoteStore,
) -> None:
    """The library's one-time copy must never touch home-guard's nodes.

    Steady state on the old prefix is a drained ``{}`` evidence node, which
    parses as an empty CRDT log. Copying it onto a pending upload at the new
    path would crash (Python) or overwrite the photos with ``{}`` and fake an
    "accepted" signal (Dart). Each gate run is a new process, so the copy
    would run every time.
    """
    remote.put_file_text(f"{SYNC_OLD_PREFIX}/evidence/current.json", "{}")
    remote.put_file_text(
        f"{SYNC_OLD_PREFIX}/challenge/current.json", '{"token": "old"}'
    )
    get_sync_client().put_file_text(
        SYNC_EVIDENCE_PATH, '{"token": "secret-token-123"}', message="phone"
    )
    reset_e2e_copy_memo()  # a fresh gate process

    assert fetch_evidence() == {"token": "secret-token-123"}
    assert remote.get_file_text(f"{SYNC_OLD_PREFIX}/evidence/current.json") == "{}"


def test_legacy_guard_delegates_everything_but_the_old_listing() -> None:
    inner = FakeRemoteStore()
    inner.put_file_text(f"{SYNC_OLD_PREFIX}/zones/current.json", "{}")
    inner.put_file_text(f"{SYNC_PREFIX}/zones/current.json", "x")
    guard = sync_client_module._NoLegacyCopy(inner)
    assert guard.list_directory(SYNC_OLD_PREFIX) == []
    assert guard.list_directory(SYNC_PREFIX) == ["zones/current.json"]
    assert guard.can_access_remote() is True
    guard.delete_file(f"{SYNC_PREFIX}/zones/current.json")
    assert inner.get_file_text(f"{SYNC_PREFIX}/zones/current.json") is None
