"""Unlimited photos, capped individually, written all-or-nothing."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest

from home_guard._constants import MAX_EVIDENCE_PHOTO_BYTES
import home_guard._evidence_photos as photos_module
from home_guard._evidence_photos import photos_in, save_evidence_photos, zone_slug

if TYPE_CHECKING:
    from pathlib import Path

_RAW = b"\xff\xd8\xffbody"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _payload(count: int, *, zone: str = "glass panel under mirror") -> dict:
    return {
        "day": "2026-09-12",
        "slot": "0800",
        "zone": zone,
        "photos": [
            {"b64": _b64(_RAW + bytes([i])), "mime": "image/jpeg"} for i in range(count)
        ],
    }


def test_writes_every_photo_with_an_indexed_name(tmp_path: Path) -> None:
    written = save_evidence_photos(_payload(5), photos_dir=tmp_path)
    assert written is not None
    assert len(written) == 5
    assert [p.name for p in written] == [
        f"2026-09-12-0800-glass-panel-under-mirror-{i:02d}.jpg" for i in range(5)
    ]
    assert written[3].read_bytes() == _RAW + bytes([3])


def test_there_is_no_upper_limit_on_the_count(tmp_path: Path) -> None:
    """A clean is however many shots it takes; only each shot is capped."""
    written = save_evidence_photos(_payload(40), photos_dir=tmp_path)
    assert written is not None
    assert len(written) == 40


def test_a_single_photo_still_works(tmp_path: Path) -> None:
    assert len(save_evidence_photos(_payload(1), photos_dir=tmp_path) or ()) == 1


def test_the_legacy_single_photo_payload_still_works(tmp_path: Path) -> None:
    """An APK that has not updated must not start failing."""
    payload = {
        "day": "2026-09-12",
        "slot": "0800",
        "zone": "desk",
        "photo_b64": _b64(_RAW),
    }
    written = save_evidence_photos(payload, photos_dir=tmp_path)
    assert written is not None
    assert written[0].name == "2026-09-12-0800-desk-00.jpg"


def test_one_oversized_photo_rejects_the_whole_set_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """Validate-all-then-write-all: no orphans nothing will ever clean up."""
    payload = _payload(3)
    payload["photos"][2]["b64"] = _b64(b"x" * (MAX_EVIDENCE_PHOTO_BYTES + 1))
    assert save_evidence_photos(payload, photos_dir=tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_one_undecodable_photo_rejects_the_whole_set(tmp_path: Path) -> None:
    payload = _payload(3)
    payload["photos"][1]["b64"] = "not base64!!"
    assert save_evidence_photos(payload, photos_dir=tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_an_empty_photo_list_is_rejected(tmp_path: Path) -> None:
    assert save_evidence_photos(_payload(0), photos_dir=tmp_path) is None


def test_missing_metadata_is_rejected(tmp_path: Path) -> None:
    assert save_evidence_photos({"day": "2026-09-12"}, photos_dir=tmp_path) is None


def test_a_nearly_full_disk_refuses_the_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no count cap, filling the disk is the real failure mode."""
    monkeypatch.setattr(photos_module, "_has_room", lambda *_a: False)
    assert save_evidence_photos(_payload(3), photos_dir=tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_disk_check_tolerates_a_stat_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_path: Path) -> None:
        raise OSError

    monkeypatch.setattr(photos_module.shutil, "disk_usage", _boom)
    assert save_evidence_photos(_payload(1), photos_dir=tmp_path) is not None


def test_photos_in_prefers_the_list_over_the_legacy_field() -> None:
    payload = {"photos": [{"b64": "a"}], "photo_b64": "legacy"}
    assert photos_in(payload) == [{"b64": "a"}]


def test_photos_in_is_empty_for_neither_shape() -> None:
    assert photos_in({}) == []
    assert photos_in({"photo_b64": ""}) == []


@pytest.mark.parametrize(
    ("zone", "expected"),
    [
        ("kitchen counter", "kitchen-counter"),
        ("  Mirror  ", "mirror"),
        ("!!!", "zone"),
        ("washing machine", "washing-machine"),
    ],
)
def test_zone_slug(zone: str, expected: str) -> None:
    assert zone_slug(zone) == expected


def test_a_photo_row_with_no_usable_b64_rejects_the_set(tmp_path: Path) -> None:
    """A dict with a missing/blank/non-string b64, and a bare non-string row."""
    for bad in ({"mime": "image/jpeg"}, {"b64": ""}, {"b64": 17}, 42, None):
        payload = _payload(2)
        payload["photos"][1] = bad
        assert save_evidence_photos(payload, photos_dir=tmp_path) is None
    assert list(tmp_path.iterdir()) == []
