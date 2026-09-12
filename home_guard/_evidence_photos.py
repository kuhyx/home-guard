"""Decode, validate and persist a clean's photos.

Split out of :mod:`home_guard._sync_evidence` when a clean stopped being one
photo. The count is deliberately **unbounded** -- a clean is however many
shots it takes, and five fixtures at three angles each is a normal bathroom
run -- so the bounds that remain are the ones that protect something real:

* every individual photo is still capped at ``MAX_EVIDENCE_PHOTO_BYTES`` on
  both ends, so no single unbounded blob can ever be written;
* free disk space is checked before anything lands, because with no count cap
  the honest failure mode is ``PHOTOS_DIR`` filling the disk, not one huge
  node.

**Validate every photo before writing any.** A payload rejected at photo 4
must leave zero files behind; a naive decode-and-write loop would leave three
orphans that no clear entry references and nothing ever cleans up.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
import shutil
from typing import TYPE_CHECKING, Any

from home_guard._constants import (
    MAX_EVIDENCE_PHOTO_BYTES,
    MIN_FREE_DISK_BYTES,
    PHOTOS_DIR,
)

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def zone_slug(zone: str) -> str:
    """Filesystem-safe form of a zone name."""
    slug = _SLUG_PATTERN.sub("-", zone.strip().lower()).strip("-")
    return slug or "zone"


def _decode_one(raw_photo: object) -> bytes | None:
    """Decode one photo entry from either the list or the legacy shape."""
    b64 = raw_photo.get("b64") if isinstance(raw_photo, dict) else raw_photo
    if not isinstance(b64, str) or not b64:
        return None
    try:
        decoded = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        _logger.warning("could not decode an evidence photo: %s", exc)
        return None
    if len(decoded) > MAX_EVIDENCE_PHOTO_BYTES:
        _logger.warning(
            "evidence photo is %d bytes, over the %d per-photo cap",
            len(decoded),
            MAX_EVIDENCE_PHOTO_BYTES,
        )
        return None
    return decoded


def photos_in(payload: dict[str, Any]) -> list[object]:
    """Return the payload's raw photo entries, new shape or legacy.

    An old APK writes a single ``photo_b64``; this keeps working forever, so
    a phone that has not updated does not start failing the day the PC does.
    """
    listed = payload.get("photos")
    if isinstance(listed, list):
        return list(listed)
    legacy = payload.get("photo_b64")
    return [legacy] if isinstance(legacy, str) and legacy else []


def _has_room(target_dir: Path, needed: int) -> bool:
    try:
        free = shutil.disk_usage(target_dir).free
    except OSError:  # pragma: no cover - stat of an existing dir we just made
        return True
    return free - needed >= MIN_FREE_DISK_BYTES


def save_evidence_photos(
    payload: dict[str, Any],
    *,
    photos_dir: Path | None = None,
) -> tuple[Path, ...] | None:
    """Persist every photo in ``payload``. ``None`` if any one is unusable.

    All-or-nothing: decode and validate the whole set first, then write.
    """
    day = payload.get("day")
    slot = payload.get("slot")
    zone = payload.get("zone")
    if not all(isinstance(v, str) and v for v in (day, slot, zone)):
        return None

    raw_photos = photos_in(payload)
    if not raw_photos:
        return None

    decoded: list[bytes] = []
    for raw in raw_photos:
        one = _decode_one(raw)
        if one is None:
            # Reject the whole payload rather than silently banking a
            # partial clean the user would have no way to notice.
            return None
        decoded.append(one)

    target_dir = photos_dir if photos_dir is not None else PHOTOS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    if not _has_room(target_dir, sum(len(d) for d in decoded)):
        _logger.warning("refusing to write %d photos: disk nearly full", len(decoded))
        return None

    slug = zone_slug(zone)
    written: list[Path] = []
    for index, blob in enumerate(decoded):
        target = target_dir / f"{day}-{slot}-{slug}-{index:02d}.jpg"
        target.write_bytes(blob)
        written.append(target)
    return tuple(written)
