"""Publish a minted challenge to Firebase RTDB, so the phone can fetch it."""

from __future__ import annotations

from dataclasses import asdict
import json
import logging
from typing import TYPE_CHECKING

from crdt_sync import RemoteStore, RemoteSyncError

from home_guard._constants import SYNC_CHALLENGE_PATH
from home_guard._sync_client import SyncUnavailableError, get_sync_client

if TYPE_CHECKING:
    from home_guard._challenge_store import ChallengeRecord

_logger = logging.getLogger(__name__)


def publish_challenge(
    record: ChallengeRecord, *, client: RemoteStore | None = None
) -> bool:
    """Publish ``record`` so the phone app can fetch it. Returns success.

    Never raises: a publish failure must let the caller fall into the
    network-incident path instead of arming a lock demanding evidence for a
    challenge the phone never saw.
    """
    try:
        target = client if client is not None else get_sync_client()
        target.put_file_text(
            SYNC_CHALLENGE_PATH,
            json.dumps(asdict(record)),
            message="home-guard challenge",
        )
    except (SyncUnavailableError, RemoteSyncError) as exc:
        _logger.warning("could not publish home-guard challenge: %s", exc)
        return False
    return True
