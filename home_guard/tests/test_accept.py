"""Tests for the full verify -> photo -> log -> rotate -> drain pipeline."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from home_guard._accept import process_evidence
from home_guard._challenge import mint_challenge
from home_guard._log import cleared_slots_today
from home_guard._paths import HomeGuardPaths
from home_guard._sync_evidence import fetch_evidence
from home_guard._zone_cursor import current_zone
from home_guard._zone_list import record_zone_list_change
from home_guard.tests.fake_remote_store import FakeRemoteStore

if TYPE_CHECKING:
    from pathlib import Path

_RAW_PHOTO = b"\xff\xd8\xff\xe0fake-jpeg"


def _paths(tmp_path: Path) -> HomeGuardPaths:
    return HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
        log_path=tmp_path / "clear_log.json",
        log_key_file=tmp_path / "no-key",
        photos_dir=tmp_path / "photos",
        zone_cursor_path=tmp_path / ".zone_cursor",
        zone_list_path=tmp_path / ".zone_list",
    )


def test_accept_full_pipeline_grants_and_rotates(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    record_zone_list_change(
        ("desk", "kitchen"), effective_from="1970-01-01", path=paths.zone_list_path
    )
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    record = mint_challenge(
        day="2026-09-06",
        slot="0800",
        zone="desk",
        now=now,
        paths=paths,
    )
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "token": record.token,
        "device_id": "phone-1",
        "photo_b64": base64.b64encode(_RAW_PHOTO).decode("ascii"),
    }
    client = FakeRemoteStore()
    result = process_evidence(payload, now=now, client=client, paths=paths)
    assert result.accepted
    assert result.photo_path is not None
    assert result.photo_path.read_bytes() == _RAW_PHOTO
    assert cleared_slots_today(
        "2026-09-06", key_file=paths.log_key_file, log_path=paths.log_path
    ) == frozenset({"0800"})
    assert (
        current_zone(
            now,
            cursor_path=paths.zone_cursor_path,
            zone_list_path=paths.zone_list_path,
        )
        == "kitchen"
    )


def test_reject_token_mismatch_has_no_side_effects(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=paths.zone_list_path
    )
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    mint_challenge(
        day="2026-09-06",
        slot="0800",
        zone="desk",
        now=now,
        paths=paths,
    )
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "token": "wrong-token",
        "photo_b64": base64.b64encode(_RAW_PHOTO).decode("ascii"),
    }
    result = process_evidence(payload, now=now, client=FakeRemoteStore(), paths=paths)
    assert not result.accepted
    assert result.reason == "token_mismatch"
    assert not paths.log_path.exists()
    assert (
        current_zone(
            now,
            cursor_path=paths.zone_cursor_path,
            zone_list_path=paths.zone_list_path,
        )
        == "desk"
    )


def test_reject_invalid_photo_does_not_grant_or_consume(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=paths.zone_list_path
    )
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    record = mint_challenge(
        day="2026-09-06",
        slot="0800",
        zone="desk",
        now=now,
        paths=paths,
    )
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "token": record.token,
        "photo_b64": "not-valid-base64!!",
    }
    result = process_evidence(payload, now=now, client=FakeRemoteStore(), paths=paths)
    assert not result.accepted
    assert result.reason == "photo_invalid"
    assert (
        cleared_slots_today(
            "2026-09-06", key_file=paths.log_key_file, log_path=paths.log_path
        )
        == frozenset()
    )


def test_accept_drains_the_evidence_node(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=paths.zone_list_path
    )
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    record = mint_challenge(
        day="2026-09-06",
        slot="0800",
        zone="desk",
        now=now,
        paths=paths,
    )
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "token": record.token,
        "photo_b64": base64.b64encode(_RAW_PHOTO).decode("ascii"),
    }
    client = FakeRemoteStore()
    from home_guard._constants import SYNC_EVIDENCE_PATH

    client.put_file_text(SYNC_EVIDENCE_PATH, "some-payload", message="")
    process_evidence(payload, now=now, client=client, paths=paths)
    assert fetch_evidence(client=client) is None


def test_no_drain_flag_leaves_evidence_untouched(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    record_zone_list_change(
        ("desk",), effective_from="1970-01-01", path=paths.zone_list_path
    )
    now = datetime(2026, 9, 6, 9, tzinfo=UTC)
    record = mint_challenge(
        day="2026-09-06",
        slot="0800",
        zone="desk",
        now=now,
        paths=paths,
    )
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "token": record.token,
        "photo_b64": base64.b64encode(_RAW_PHOTO).decode("ascii"),
    }
    client = FakeRemoteStore()
    result = process_evidence(payload, now=now, client=client, drain=False, paths=paths)
    assert result.accepted
