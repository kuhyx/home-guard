"""The one non-mutating way to read a clear entry's photos.

Two shapes exist and **both must keep verifying forever**:

* legacy, one photo: ``photo_path`` + ``photo_bytes``
* current, N photos: ``photos: [{"path": ..., "bytes": ...}]`` + ``photo_count``

``gatelock.log_integrity.verify_entry_hmac`` recomputes the signature over
whatever dict is actually stored (every key except ``hmac``, ``sort_keys``).
It therefore signs the *field names* as much as the values, so an old entry
verifies unchanged and a new one verifies unchanged -- no migration exists or
is needed.

The corollary is the rule this module exists to enforce: **never normalise,
upgrade or rewrite an entry dict before handing it to
:func:`home_guard._log.is_valid_clear_entry`.** "Helpfully" converting a
legacy entry to the new shape would invalidate its signature and silently
void a real, already-earned clear. Reading photos goes through
:func:`photos_of`, which copies nothing back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class PhotoRef:
    """One stored photo: where it is, and how big it was."""

    path: str
    bytes_on_disk: int


def _ref_from_raw(raw: object) -> PhotoRef | None:
    if not isinstance(raw, dict):
        return None
    path = raw.get("path")
    size = raw.get("bytes")
    if not isinstance(path, str) or not path or not isinstance(size, int):
        return None
    return PhotoRef(path=path, bytes_on_disk=size)


def photos_of(entry: Mapping[str, Any]) -> tuple[PhotoRef, ...]:
    """Return an entry's photos, whichever shape it was written in.

    Returns ``()`` for an entry with neither (an ``escape`` entry, or a
    corrupt one) rather than raising -- a reader rendering history must not
    die on one bad row.
    """
    raw_photos = entry.get("photos")
    if isinstance(raw_photos, list):
        return tuple(
            ref for item in raw_photos if (ref := _ref_from_raw(item)) is not None
        )
    path = entry.get("photo_path")
    size = entry.get("photo_bytes")
    if isinstance(path, str) and path and isinstance(size, int):
        return (PhotoRef(path=path, bytes_on_disk=size),)
    return ()
