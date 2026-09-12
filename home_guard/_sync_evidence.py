"""Fetch and drain the evidence RTDB node.

RTDB is transport only, never storage: a payload lands here just long enough
to be read, then the node is drained (overwritten with ``{}``) so it cannot
be replayed against a future slot and does not sit there as a growing blob.

Decoding and persisting the photos themselves lives in
:mod:`home_guard._evidence_photos`, which is where the all-or-nothing write
ordering and the per-photo cap are enforced.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from crdt_sync import RemoteStore, RemoteSyncError

from home_guard._constants import SYNC_EVIDENCE_PATH
from home_guard._sync_client import SyncUnavailableError, get_sync_client

_logger = logging.getLogger(__name__)

_DRAIN_PAYLOAD = "{}"


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
