"""Tests for the publish-then-echo anti-replay mechanism."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gatelock.log_integrity import generate_hmac_key

from home_guard._challenge import consume_challenge, mint_challenge, verify_evidence
from home_guard._challenge_store import get_challenge
from home_guard._paths import HomeGuardPaths

if TYPE_CHECKING:
    from pathlib import Path


def test_mint_creates_a_token(tmp_path: Path) -> None:
    paths = HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
    )
    record = mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    assert record.token
    assert not record.consumed


def test_mint_is_idempotent_same_token(tmp_path: Path) -> None:
    paths = HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
    )
    first = mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    second = mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    assert first.token == second.token


def test_verify_accepts_matching_echo(tmp_path: Path) -> None:
    paths = HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
    )
    record = mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "token": record.token,
    }
    result = verify_evidence(
        payload, path=paths.challenge_path, key_file=paths.challenge_key_file
    )
    assert result.accepted
    assert result.reason is None


def test_verify_rejects_no_challenge(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    key_file = tmp_path / "no-key"
    payload = {"day": "2026-09-06", "slot": "0800", "zone": "desk", "token": "whatever"}
    result = verify_evidence(payload, path=path, key_file=key_file)
    assert not result.accepted
    assert result.reason == "no_challenge"


def test_verify_rejects_missing_day_or_slot_fields(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    key_file = tmp_path / "no-key"
    result = verify_evidence(
        {"zone": "desk", "token": "x"}, path=path, key_file=key_file
    )
    assert not result.accepted
    assert result.reason == "no_challenge"


def test_verify_rejects_token_mismatch(tmp_path: Path) -> None:
    paths = HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
    )
    mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    payload = {"day": "2026-09-06", "slot": "0800", "zone": "desk", "token": "wrong"}
    result = verify_evidence(
        payload, path=paths.challenge_path, key_file=paths.challenge_key_file
    )
    assert not result.accepted
    assert result.reason == "token_mismatch"


def test_verify_rejects_zone_mismatch(tmp_path: Path) -> None:
    paths = HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
    )
    record = mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "kitchen",
        "token": record.token,
    }
    result = verify_evidence(
        payload, path=paths.challenge_path, key_file=paths.challenge_key_file
    )
    assert not result.accepted
    assert result.reason == "zone_mismatch"


def test_verify_rejects_already_consumed_replay(tmp_path: Path) -> None:
    paths = HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
    )
    record = mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    consume_challenge(
        record, path=paths.challenge_path, key_file=paths.challenge_key_file
    )
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "token": record.token,
    }
    result = verify_evidence(
        payload, path=paths.challenge_path, key_file=paths.challenge_key_file
    )
    assert not result.accepted
    assert result.reason == "already_consumed"


def test_consume_marks_record_consumed(tmp_path: Path) -> None:
    paths = HomeGuardPaths(
        challenge_path=tmp_path / "challenges.json",
        challenge_key_file=tmp_path / "no-key",
    )
    record = mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    consume_challenge(
        record, path=paths.challenge_path, key_file=paths.challenge_key_file
    )
    stored = get_challenge(
        "2026-09-06",
        "0800",
        path=paths.challenge_path,
        key_file=paths.challenge_key_file,
    )
    assert stored is not None
    assert stored.consumed


def test_tampered_challenge_store_is_discarded(tmp_path: Path) -> None:
    path = tmp_path / "challenges.json"
    key_file = tmp_path / "hmac.key"
    generate_hmac_key(key_file)
    paths = HomeGuardPaths(challenge_path=path, challenge_key_file=key_file)
    record = mint_challenge(day="2026-09-06", slot="0800", zone="desk", paths=paths)
    # Hand-edit the persisted file to flip consumed back to false.
    import json

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["2026-09-06:0800"]["consumed"] = True
    path.write_text(json.dumps(raw), encoding="utf-8")
    payload = {
        "day": "2026-09-06",
        "slot": "0800",
        "zone": "desk",
        "token": record.token,
    }
    result = verify_evidence(payload, path=path, key_file=key_file)
    # The tampered record is dropped entirely on load, so this reads as "no
    # challenge" rather than trusting the hand-edited consumed flag either way.
    assert not result.accepted
    assert result.reason == "no_challenge"
