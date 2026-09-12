"""Both clear-entry photo shapes must stay readable, and stay verifiable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gatelock.log_integrity import compute_entry_hmac

from home_guard._clear_photos import PhotoRef, photos_of
from home_guard._log import ClearEntryData, append_clear_entry, is_valid_clear_entry
from home_guard._log_store import read_raw_log

if TYPE_CHECKING:
    from pathlib import Path

# The challenge echo under test. A name rather than an inline literal, so
# ruff's S105/S106 (hardcoded password) never trips on a value that is not one.
_ECHO = "tok"
_ECHO_NEW = "tok2"

_LEGACY = {
    "kind": "clear",
    "slot": "0800",
    "zone": "desk",
    "device": "phone",
    "logged_at": "2026-09-06T08:00:00+00:00",
    "photo_path": "photos/old.jpg",
    "photo_bytes": 1234,
    "token": _ECHO,
}


def test_reads_the_legacy_scalar_shape() -> None:
    assert photos_of(_LEGACY) == (PhotoRef(path="photos/old.jpg", bytes_on_disk=1234),)


def test_reads_the_current_list_shape() -> None:
    entry = {
        "photos": [
            {"path": "a.jpg", "bytes": 1},
            {"path": "b.jpg", "bytes": 2},
        ]
    }
    assert [p.path for p in photos_of(entry)] == ["a.jpg", "b.jpg"]


def test_the_list_shape_wins_when_both_are_present() -> None:
    entry = {**_LEGACY, "photos": [{"path": "new.jpg", "bytes": 9}]}
    assert [p.path for p in photos_of(entry)] == ["new.jpg"]


def test_an_entry_with_no_photos_is_empty_not_an_error() -> None:
    assert photos_of({"kind": "escape", "slot": "0800"}) == ()


def test_malformed_photo_rows_are_skipped() -> None:
    entry = {
        "photos": [
            {"path": "ok.jpg", "bytes": 1},
            {"path": "", "bytes": 1},
            {"path": "no-size.jpg"},
            "garbage",
            {"path": "bad-size.jpg", "bytes": "1"},
        ]
    }
    assert [p.path for p in photos_of(entry)] == ["ok.jpg"]


def test_a_legacy_entry_still_verifies_beside_a_new_one(tmp_path: Path) -> None:
    """The guarantee that makes this migration-free.

    verify_entry_hmac signs whatever dict is stored, field names included, so
    an entry written before multi-photo existed must keep verifying forever.
    If this ever fails, some reader "helpfully" normalised an entry before
    verifying it and voided a real, already-earned clear.
    """
    key_file = tmp_path / "hmac.key"
    key_file.write_bytes(b"0" * 32)
    log_path = tmp_path / "clear_log.json"

    legacy = {**_LEGACY}
    legacy["hmac"] = compute_entry_hmac(legacy, key_file=key_file)
    assert is_valid_clear_entry(legacy, key_file=key_file) is True

    append_clear_entry(
        ClearEntryData(
            slot="0800",
            zone="mirror",
            device="phone",
            photos=(
                PhotoRef(path="a.jpg", bytes_on_disk=1),
                PhotoRef(path="b.jpg", bytes_on_disk=2),
            ),
            token=_ECHO_NEW,
        ),
        key_file=key_file,
        log_path=log_path,
    )
    stored = next(iter(read_raw_log(log_path).values()))[0]
    assert is_valid_clear_entry(stored, key_file=key_file) is True
    assert len(photos_of(stored)) == 2
    assert stored["photo_count"] == 2
    # A new entry must NOT also carry the legacy fields: two competing
    # answers to "which photo is authoritative" inside a signed record.
    assert "photo_path" not in stored
