"""Edge-case coverage for the raw challenge-store persistence layer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from gatelock.log_integrity import generate_hmac_key

from home_guard._challenge_store import ChallengeRecord, load_challenges, put_challenge

if TYPE_CHECKING:
    from pathlib import Path

# The challenge echo under test. A name rather than an inline literal, so
# ruff's S105/S106 (hardcoded password) never trips on a value that is not one.
_ECHO = "t"


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    assert (
        load_challenges(tmp_path / "missing.json", key_file=tmp_path / "no-key") == {}
    )


def test_load_corrupt_json_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    path.write_text("not json", encoding="utf-8")
    assert load_challenges(path, key_file=tmp_path / "no-key") == {}


def test_load_non_dict_top_level_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    path.write_text("[]", encoding="utf-8")
    assert load_challenges(path, key_file=tmp_path / "no-key") == {}


def test_load_skips_non_string_key_or_non_dict_payload(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    path.write_text(json.dumps({"ok": "not-a-dict"}), encoding="utf-8")
    assert load_challenges(path, key_file=tmp_path / "no-key") == {}


def test_load_skips_record_missing_required_field(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    path.write_text(
        json.dumps({"2026-09-06:0800": {"day": "2026-09-06", "slot": "0800"}}),
        encoding="utf-8",
    )
    assert load_challenges(path, key_file=tmp_path / "no-key") == {}


def test_load_skips_record_with_non_bool_consumed(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    path.write_text(
        json.dumps(
            {
                "2026-09-06:0800": {
                    "day": "2026-09-06",
                    "slot": "0800",
                    "zone": "desk",
                    "token": "t",
                    "issued_at": "now",
                    "consumed": "not-a-bool",
                }
            }
        ),
        encoding="utf-8",
    )
    assert load_challenges(path, key_file=tmp_path / "no-key") == {}


def test_load_discards_record_missing_hmac_when_key_exists(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    key_file = tmp_path / "hmac.key"
    generate_hmac_key(key_file)
    path.write_text(
        json.dumps(
            {
                "2026-09-06:0800": {
                    "day": "2026-09-06",
                    "slot": "0800",
                    "zone": "desk",
                    "token": "t",
                    "issued_at": "now",
                    "consumed": False,
                }
            }
        ),
        encoding="utf-8",
    )
    # A record with no "hmac" field at all, once a signing key exists, is
    # treated the same as a failed signature -- not as "predates the key".
    assert load_challenges(path, key_file=key_file) == {}


def test_load_keeps_valid_signed_record(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    key_file = tmp_path / "hmac.key"
    generate_hmac_key(key_file)
    record = ChallengeRecord(
        day="2026-09-06",
        slot="0800",
        zone="desk",
        token=_ECHO,
        issued_at="now",
        consumed=False,
    )
    put_challenge(record, path=path, key_file=key_file)
    loaded = load_challenges(path, key_file=key_file)
    assert loaded["2026-09-06:0800"] == record
