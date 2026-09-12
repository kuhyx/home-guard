"""Tests for the HMAC-signed, asymmetrically-verified clear/escape log."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gatelock.log_integrity import generate_hmac_key

from home_guard._clear_photos import PhotoRef, photos_of
from home_guard._log import (
    ClearEntryData,
    EscapeEntryData,
    append_clear_entry,
    append_escape_entry,
    cleared_slots_today,
    is_valid_clear_entry,
    recent_entries,
)
from home_guard._log_store import read_raw_log

if TYPE_CHECKING:
    from pathlib import Path

# The challenge echo under test. A name rather than an inline literal, so
# ruff's S105/S106 (hardcoded password) never trips on a value that is not one.
_ECHO = "tok"
_ECHO_1 = "t1"
_ECHO_2 = "t2"


def test_clear_entry_with_no_key_counts_unsigned(tmp_path: Path) -> None:
    log_path = tmp_path / "clear_log.json"
    missing_key = tmp_path / "no-such-key"
    now = datetime(2026, 9, 6, 9, 5, tzinfo=UTC)
    append_clear_entry(
        ClearEntryData(
            slot="0800",
            zone="desk",
            device="phone-1",
            photos=(PhotoRef(path="photos/x.jpg", bytes_on_disk=1234),),
            token=_ECHO,
        ),
        now=now,
        key_file=missing_key,
        log_path=log_path,
    )
    cleared = cleared_slots_today("2026-09-06", key_file=missing_key, log_path=log_path)
    assert cleared == frozenset({"0800"})


def test_clear_entry_is_signed_when_key_exists(tmp_path: Path) -> None:
    key_file = tmp_path / "hmac.key"
    generate_hmac_key(key_file)
    log_path = tmp_path / "clear_log.json"
    now = datetime(2026, 9, 6, 9, 5, tzinfo=UTC)
    entry = append_clear_entry(
        ClearEntryData(
            slot="0800",
            zone="desk",
            device="phone-1",
            photos=(PhotoRef(path="photos/x.jpg", bytes_on_disk=1234),),
            token=_ECHO,
        ),
        now=now,
        key_file=key_file,
        log_path=log_path,
    )
    assert "hmac" in entry
    assert is_valid_clear_entry(entry, key_file=key_file)
    cleared = cleared_slots_today("2026-09-06", key_file=key_file, log_path=log_path)
    assert cleared == frozenset({"0800"})


def test_tampered_clear_entry_does_not_count(tmp_path: Path) -> None:
    key_file = tmp_path / "hmac.key"
    generate_hmac_key(key_file)
    log_path = tmp_path / "clear_log.json"
    now = datetime(2026, 9, 6, 9, 5, tzinfo=UTC)
    append_clear_entry(
        ClearEntryData(
            slot="0800",
            zone="desk",
            device="phone-1",
            photos=(PhotoRef(path="photos/x.jpg", bytes_on_disk=1234),),
            token=_ECHO,
        ),
        now=now,
        key_file=key_file,
        log_path=log_path,
    )
    log = read_raw_log(log_path)
    log["2026-09-06"][0]["zone"] = "kitchen"  # hand-edit after signing
    from home_guard._log_store import write_log

    write_log(log, log_path)
    cleared = cleared_slots_today("2026-09-06", key_file=key_file, log_path=log_path)
    assert cleared == frozenset()


def test_escape_entry_counts_even_without_key(tmp_path: Path) -> None:
    log_path = tmp_path / "clear_log.json"
    missing_key = tmp_path / "no-such-key"
    now = datetime(2026, 9, 6, 9, 5, tzinfo=UTC)
    append_escape_entry(
        EscapeEntryData(
            slot="0800",
            zone="desk",
            reason="firebase unreachable, justified via the hatch",
        ),
        now=now,
        key_file=missing_key,
        log_path=log_path,
    )
    cleared = cleared_slots_today("2026-09-06", key_file=missing_key, log_path=log_path)
    assert cleared == frozenset({"0800"})


def test_escape_entry_counts_even_if_tampered(tmp_path: Path) -> None:
    key_file = tmp_path / "hmac.key"
    generate_hmac_key(key_file)
    log_path = tmp_path / "clear_log.json"
    now = datetime(2026, 9, 6, 9, 5, tzinfo=UTC)
    append_escape_entry(
        EscapeEntryData(
            slot="0800",
            zone="desk",
            reason="firebase unreachable, justified via the hatch",
        ),
        now=now,
        key_file=key_file,
        log_path=log_path,
    )
    log = read_raw_log(log_path)
    log["2026-09-06"][0]["reason"] = "edited"
    from home_guard._log_store import write_log

    write_log(log, log_path)
    # escape entries count regardless of signature state -- their abuse
    # resistance is the hatch's own rolling budget, not this log's HMAC.
    cleared = cleared_slots_today("2026-09-06", key_file=key_file, log_path=log_path)
    assert cleared == frozenset({"0800"})


def test_recent_entries_newest_first_across_days(tmp_path: Path) -> None:
    log_path = tmp_path / "clear_log.json"
    key_file = tmp_path / "no-such-key"
    append_clear_entry(
        ClearEntryData(
            slot="0800",
            zone="desk",
            device="d",
            photos=(PhotoRef(path="p1", bytes_on_disk=1),),
            token=_ECHO_1,
        ),
        now=datetime(2026, 9, 5, 9, tzinfo=UTC),
        key_file=key_file,
        log_path=log_path,
    )
    append_clear_entry(
        ClearEntryData(
            slot="0800",
            zone="desk",
            device="d",
            photos=(PhotoRef(path="p2", bytes_on_disk=1),),
            token=_ECHO_2,
        ),
        now=datetime(2026, 9, 6, 9, tzinfo=UTC),
        key_file=key_file,
        log_path=log_path,
    )
    entries = recent_entries(limit=1, log_path=log_path)
    assert len(entries) == 1
    assert photos_of(entries[0])[0].path == "p2"


def test_read_raw_log_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_raw_log(tmp_path / "missing.json") == {}


def test_read_raw_log_corrupt_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "clear_log.json"
    path.write_text("not json", encoding="utf-8")
    assert read_raw_log(path) == {}


def test_read_raw_log_non_dict_top_level_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "clear_log.json"
    path.write_text("[]", encoding="utf-8")
    assert read_raw_log(path) == {}


def test_cleared_slots_today_ignores_non_string_slot(tmp_path: Path) -> None:
    log_path = tmp_path / "clear_log.json"
    from home_guard._log_store import write_log

    write_log({"2026-09-06": [{"kind": "clear", "slot": 42}]}, log_path)
    assert cleared_slots_today("2026-09-06", log_path=log_path) == frozenset()
