"""Fetch and drain the evidence RTDB node; persist an accepted photo to disk.

RTDB is transport only, never storage: a photo lands here just long enough
to be read, decoded and written under ``PHOTOS_DIR``, then the node is
drained (overwritten with ``{}``) so it cannot be replayed against a future
slot and does not sit there as a growing blob.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from typing import TYPE_CHECKING, Any

from crdt_sync import RemoteStore, RemoteSyncError

from home_guard._constants import (
    MAX_EVIDENCE_PHOTO_BYTES,
    PHOTOS_DIR,
    SYNC_EVIDENCE_PATH,
)
from home_guard._sync_client import SyncUnavailableError, get_sync_client

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)

_DRAIN_PAYLOAD = "{}"
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def fetch_evidence(*, client: RemoteStore | None = None) -> dict[str, Any] | None:
    """Return the current evidence payload, or None if absent/unreachable/empty."""
    try:
        target = client if client is not None else get_sync_client()
        text = target.get_file_text(SYNC_EVIDENCE_PATH)
    except (SyncUnavailableError, RemoteSyncError) as exc:
        _logger.debug("could not fetch home-guard evidence: %s", exc)
        return None
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload:
        return None
    return payload


def drain_evidence(*, client: RemoteStore | None = None) -> bool:
    """Overwrite the evidence node with an empty payload. Returns success."""
    try:
        target = client if client is not None else get_sync_client()
        target.put_file_text(
            SYNC_EVIDENCE_PATH, _DRAIN_PAYLOAD, message="home-guard evidence drained"
        )
    except (SyncUnavailableError, RemoteSyncError) as exc:
        _logger.warning("could not drain home-guard evidence: %s", exc)
        return False
    return True


def _zone_slug(zone: str) -> str:
    slug = _SLUG_PATTERN.sub("-", zone.strip().lower()).strip("-")
    return slug or "zone"


def save_evidence_photo(
    payload: dict[str, Any],
    *,
    photos_dir: Path | None = None,
) -> Path | None:
    """Decode ``photo_b64`` and write it under ``photos_dir``. None on failure."""
    photo_b64 = payload.get("photo_b64")
    day = payload.get("day")
    slot = payload.get("slot")
    zone = payload.get("zone")
    if not all(isinstance(v, str) and v for v in (photo_b64, day, slot, zone)):
        return None
    try:
        raw = base64.b64decode(photo_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        _logger.warning("could not decode evidence photo: %s", exc)
        return None
    if len(raw) > MAX_EVIDENCE_PHOTO_BYTES:
        _logger.warning(
            "evidence photo is %d bytes, over the %d cap -- refusing to write it",
            len(raw),
            MAX_EVIDENCE_PHOTO_BYTES,
        )
        return None
    target_dir = photos_dir if photos_dir is not None else PHOTOS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{day}-{slot}-{_zone_slug(zone)}.jpg"
    target = target_dir / filename
    target.write_bytes(raw)
    return target
