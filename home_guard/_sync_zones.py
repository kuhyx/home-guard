"""Fetch and publish the zone-list history over Firebase RTDB.

Carries the whole forward-only history in ``.zone_list``'s own on-disk shape,
so both sides can merge with a plain dict union (:mod:`home_guard._zone_merge`)
instead of inventing a second representation that could drift from the file.

Never raises. Arming must never depend on the network -- that is
``_network_incident.py``'s entire docstring -- so every failure here is a
debug log and a ``None``/``False``, and the caller carries on with whatever it
already had on disk.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from crdt_sync import RemoteStore, RemoteSyncError

from home_guard._constants import SYNC_ZONES_PATH
from home_guard._sync_client import SyncUnavailableError, get_sync_client
from home_guard._zone_list import entries_from_payload, payload_from_entries

if TYPE_CHECKING:
    from home_guard._zone_list import ZoneListEntry

_logger = logging.getLogger(__name__)


def fetch_zone_history(
    *, client: RemoteStore | None = None
) -> tuple[ZoneListEntry, ...] | None:
    """Return the published history, or ``None`` if absent/unreachable/garbage.

    ``None`` and ``()`` mean different things on purpose: ``None`` is "could
    not see it, keep what you have", ``()`` is "saw it, it is empty".
    """
    try:
        target = client if client is not None else get_sync_client()
        text = target.get_file_text(SYNC_ZONES_PATH)
    except (SyncUnavailableError, RemoteSyncError) as exc:
        # ConfigError does NOT subclass RemoteSyncError -- caught explicitly
        # below via SyncUnavailableError, per _sync_client.py's documented
        # gotcha. Losing that distinction is how diet-guard's own sync broke.
        _logger.debug("could not fetch home-guard zones: %s", exc)
        return None
    if not text:
        return None
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        _logger.warning("published zone history is not valid JSON; ignoring it")
        return None
    return entries_from_payload(payload)


def publish_zone_history(
    entries: tuple[ZoneListEntry, ...], *, client: RemoteStore | None = None
) -> bool:
    """Publish ``entries`` for the phone to merge. Returns success."""
    try:
        target = client if client is not None else get_sync_client()
        target.put_file_text(
            SYNC_ZONES_PATH,
            json.dumps(payload_from_entries(entries)),
            message="home-guard zone rotation",
        )
    except (SyncUnavailableError, RemoteSyncError) as exc:
        _logger.warning("could not publish home-guard zones: %s", exc)
        return False
    return True
