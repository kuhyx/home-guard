"""Free zone choice, multi-photo evidence, and captured-day bucketing."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from home_guard._accept import process_evidence
from home_guard._challenge import mint_challenge
from home_guard._clear_photos import photos_of
from home_guard._log import cleared_slots_today
from home_guard._log_store import read_raw_log
from home_guard._paths import HomeGuardPaths
from home_guard._zone_cursor import current_zone, load_cursor
from home_guard._zone_list import record_zone_list_change

if TYPE_CHECKING:
    from pathlib import Path

_RAW = b"\xff\xd8\xff\xe0fake-jpeg"
_ROTATION = ("desk", "kitchen counter", "mirror", "toilet")


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


def _setup(tmp_path: Path, now: datetime) -> tuple[HomeGuardPaths, str]:
    paths = _paths(tmp_path)
    record_zone_list_change(
        _ROTATION, effective_from="1970-01-01", path=paths.zone_list_path
    )
    record = mint_challenge(
        day=now.strftime("%Y-%m-%d"),
        slot="0800",
        # The PC is waiting on "desk" in every one of these tests.
        zone="desk",
        now=now,
        paths=paths,
    )
    return paths, record.token


def _payload(token: str, zone: str, day: str, count: int = 1, **extra: object) -> dict:
    return {
        "day": day,
        "slot": "0800",
        "zone": zone,
        "token": token,
        "device_id": "phone-1",
        "photos": [
            {"b64": base64.b64encode(_RAW + bytes([i])).decode("ascii")}
            for i in range(count)
        ],
        **extra,
    }


def test_cleaning_a_different_zone_is_accepted(tmp_path: Path) -> None:
    """Five photos of a mirror must not be thrown away because the cursor
    happened to point at the desk."""
    now = datetime(2026, 9, 12, 9, tzinfo=UTC).astimezone()
    paths, token = _setup(tmp_path, now)
    result = process_evidence(
        _payload(token, "mirror", "2026-09-12", count=5),
        now=now,
        paths=paths,
        drain=False,
    )
    assert result.accepted is True
    assert len(result.photo_paths) == 5


def test_the_entry_records_the_zone_actually_cleaned(tmp_path: Path) -> None:
    now = datetime(2026, 9, 12, 9, tzinfo=UTC).astimezone()
    paths, token = _setup(tmp_path, now)
    process_evidence(
        _payload(token, "mirror", "2026-09-12"), now=now, paths=paths, drain=False
    )
    entry = next(iter(read_raw_log(paths.log_path).values()))[0]
    # Not "desk": a log saying otherwise would be a lie the photos contradict.
    assert entry["zone"] == "mirror"


def test_the_cursor_jumps_past_the_zone_cleaned(tmp_path: Path) -> None:
    now = datetime(2026, 9, 12, 9, tzinfo=UTC).astimezone()
    paths, token = _setup(tmp_path, now)
    process_evidence(
        _payload(token, "mirror", "2026-09-12"), now=now, paths=paths, drain=False
    )
    # "mirror" is index 2, so next up is index 3 -- not index 1.
    assert current_zone(now, paths=paths) == "toilet"


def test_a_zone_not_in_the_rotation_is_still_rejected(tmp_path: Path) -> None:
    """The picker and the list stay the single source of truth."""
    now = datetime(2026, 9, 12, 9, tzinfo=UTC).astimezone()
    paths, token = _setup(tmp_path, now)
    result = process_evidence(
        _payload(token, "the neighbour's garage", "2026-09-12"),
        now=now,
        paths=paths,
        drain=False,
    )
    assert result.accepted is False
    assert result.reason == "zone_mismatch"


def test_multi_photo_entry_carries_every_photo(tmp_path: Path) -> None:
    now = datetime(2026, 9, 12, 9, tzinfo=UTC).astimezone()
    paths, token = _setup(tmp_path, now)
    process_evidence(
        _payload(token, "toilet", "2026-09-12", count=7),
        now=now,
        paths=paths,
        drain=False,
    )
    entry = next(iter(read_raw_log(paths.log_path).values()))[0]
    assert entry["photo_count"] == 7
    assert len(photos_of(entry)) == 7


def test_a_clean_captured_today_unlocks_today(tmp_path: Path) -> None:
    now = datetime(2026, 9, 12, 19, tzinfo=UTC).astimezone()
    paths, token = _setup(tmp_path, now)
    payload = _payload(token, "mirror", "2026-09-12", captured_at=now.isoformat())
    assert process_evidence(payload, now=now, paths=paths, drain=False).accepted
    day = now.strftime("%Y-%m-%d")
    assert "0800" in cleared_slots_today(
        day, key_file=paths.log_key_file, log_path=paths.log_path
    )


def test_a_session_queued_yesterday_lands_in_yesterdays_bucket(
    tmp_path: Path,
) -> None:
    """The backdating rule, for free.

    A clean done while the PC was off keeps its record and its rotation
    advance, but grants nothing today -- cleared_slots_today only ever reads
    today's bucket, so there is no rule to write.
    """
    now = datetime(2026, 9, 12, 9, tzinfo=UTC).astimezone()
    paths, token = _setup(tmp_path, now)
    yesterday = now - timedelta(days=1)
    payload = _payload(token, "mirror", "2026-09-12", captured_at=yesterday.isoformat())
    assert process_evidence(payload, now=now, paths=paths, drain=False).accepted

    log = read_raw_log(paths.log_path)
    assert yesterday.strftime("%Y-%m-%d") in log
    assert "0800" not in cleared_slots_today(
        now.strftime("%Y-%m-%d"), key_file=paths.log_key_file, log_path=paths.log_path
    )
    # The rotation still moved: the cleaning really happened.
    assert load_cursor(paths.zone_cursor_path).last_slot is not None


def test_a_future_captured_at_is_clamped_to_now(tmp_path: Path) -> None:
    """A fast phone clock must not pre-satisfy a slot that has not happened."""
    now = datetime(2026, 9, 12, 9, tzinfo=UTC).astimezone()
    paths, token = _setup(tmp_path, now)
    payload = _payload(
        token, "mirror", "2026-09-12", captured_at=(now + timedelta(days=3)).isoformat()
    )
    assert process_evidence(payload, now=now, paths=paths, drain=False).accepted
    assert list(read_raw_log(paths.log_path)) == [now.strftime("%Y-%m-%d")]


def test_a_garbage_captured_at_falls_back_to_now(tmp_path: Path) -> None:
    now = datetime(2026, 9, 12, 9, tzinfo=UTC).astimezone()
    for bad in ("", "not-a-date", "2026-09-12T09:00:00", 17):
        paths2, token2 = _setup(tmp_path / str(bad), now)
        payload = _payload(token2, "mirror", "2026-09-12", captured_at=bad)
        assert process_evidence(payload, now=now, paths=paths2, drain=False).accepted
        assert list(read_raw_log(paths2.log_path)) == [now.strftime("%Y-%m-%d")]


def test_the_day_bucket_is_local_not_utc(tmp_path: Path) -> None:
    """A 00:30-local clean must not be filed under yesterday.

    _gate.py derives its day with .astimezone() while _log.py buckets by
    whatever datetime it is handed; a UTC-derived day silently mis-files
    everything captured after local midnight in a UTC+N timezone.
    """
    local = datetime(2026, 9, 12, 0, 30).astimezone()
    paths, token = _setup(tmp_path, local)
    payload = _payload(
        token, "mirror", local.strftime("%Y-%m-%d"), captured_at=local.isoformat()
    )
    assert process_evidence(payload, now=local, paths=paths, drain=False).accepted
    assert list(read_raw_log(paths.log_path)) == [local.strftime("%Y-%m-%d")]
