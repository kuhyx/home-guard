"""Atomic, HMAC-signed persistence for challenge records.

This file is the **sole authority** for anti-replay: RTDB only ever carries a
copy in transit. Each record is signed with home-guard's own key so a
hand-edited ``consumed: false`` (to replay an already-accepted upload) or a
hand-edited ``token`` (to match a forged evidence payload) is detectable and
treated as untrustworthy rather than honored.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Any

from gatelock.log_integrity import compute_entry_hmac, verify_entry_hmac

from home_guard._constants import CHALLENGE_STORE_FILE, HMAC_KEY_FILE

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChallengeRecord:
    """One slot's issued challenge."""

    day: str
    slot: str
    zone: str
    token: str
    issued_at: str
    consumed: bool


def _key(day: str, slot: str) -> str:
    return f"{day}:{slot}"


def _record_to_payload(record: ChallengeRecord) -> dict[str, Any]:
    return {
        "day": record.day,
        "slot": record.slot,
        "zone": record.zone,
        "token": record.token,
        "issued_at": record.issued_at,
        "consumed": record.consumed,
    }


def _payload_to_record(payload: dict[str, Any]) -> ChallengeRecord | None:
    required = ("day", "slot", "zone", "token", "issued_at", "consumed")
    if not all(key in payload for key in required):
        return None
    if not isinstance(payload["consumed"], bool):
        return None
    return ChallengeRecord(
        day=payload["day"],
        slot=payload["slot"],
        zone=payload["zone"],
        token=payload["token"],
        issued_at=payload["issued_at"],
        consumed=payload["consumed"],
    )


def _is_tampered(payload: dict[str, Any], *, key_file: Path) -> bool:
    """Whether a stored record's HMAC fails verification.

    Only meaningful once a key exists -- a record signed before the key was
    generated is not a forgery, mirroring the log's own discriminator.
    """
    if not key_file.is_file():
        return False
    if "hmac" not in payload:
        return True
    return not verify_entry_hmac(payload, key_file=key_file)


def load_challenges(
    path: Path | None = None,
    *,
    key_file: Path | None = None,
) -> dict[str, ChallengeRecord]:
    """Read every stored challenge record, keyed by ``day:slot``.

    A record whose HMAC fails verification is dropped -- unlike the clear
    log (where dropping would widen a budget), a tampered *challenge* has no
    legitimate use once its integrity is in doubt.
    """
    target = path if path is not None else CHALLENGE_STORE_FILE
    target_key = key_file if key_file is not None else HMAC_KEY_FILE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        _logger.warning("could not read challenge store %s: %s", target, exc)
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, ChallengeRecord] = {}
    for key, payload in raw.items():
        if not isinstance(key, str) or not isinstance(payload, dict):
            continue
        if _is_tampered(payload, key_file=target_key):
            _logger.error(
                "challenge record %r failed its HMAC check -- discarding it "
                "rather than trusting a hand-edited state file",
                key,
            )
            continue
        record = _payload_to_record(payload)
        if record is not None:
            result[key] = record
    return result


def save_challenges(
    records: dict[str, ChallengeRecord],
    path: Path | None = None,
    *,
    key_file: Path | None = None,
) -> None:
    """Sign and atomically persist every record."""
    target = path if path is not None else CHALLENGE_STORE_FILE
    target_key = key_file if key_file is not None else HMAC_KEY_FILE
    raw: dict[str, Any] = {}
    for key, record in records.items():
        payload = _record_to_payload(record)
        signature = compute_entry_hmac(payload, key_file=target_key)
        raw[key] = {**payload, "hmac": signature} if signature is not None else payload
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    tmp.replace(target)


def get_challenge(
    day: str,
    slot: str,
    *,
    path: Path | None = None,
    key_file: Path | None = None,
) -> ChallengeRecord | None:
    """Return the record for ``day:slot``, or None if never minted."""
    return load_challenges(path, key_file=key_file).get(_key(day, slot))


def put_challenge(
    record: ChallengeRecord,
    *,
    path: Path | None = None,
    key_file: Path | None = None,
) -> None:
    """Insert or replace one record and persist the whole store."""
    records = load_challenges(path, key_file=key_file)
    records[_key(record.day, record.slot)] = record
    save_challenges(records, path, key_file=key_file)
