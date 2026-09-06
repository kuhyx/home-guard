"""Choosing the Firebase RTDB client home-guard's sync calls will use.

``ConfigError`` subclasses ``Exception`` directly rather than
``RemoteSyncError`` -- a gotcha diet-guard's own ``_sync_client.py`` flags
explicitly and had bitten that file before. Every caller here catches both
explicitly rather than assuming one covers the other, so an unconfigured
Firebase setup never throws a raw traceback out of a fullscreen lock.
"""

from __future__ import annotations

import logging

from crdt_sync import ConfigError, FirebaseAuthError, RemoteStore, firebase_client_for

from home_guard._constants import APP_NAME

_logger = logging.getLogger(__name__)


class SyncUnavailableError(Exception):
    """Raised when no usable Firebase client could be built right now."""


def get_sync_client() -> RemoteStore:
    """Return a signed-in Firebase client, or raise :class:`SyncUnavailableError`.

    Neither an unconfigured setup nor a rejected credential is a bug in this
    app -- both mean "this machine cannot sync right now", which callers must
    treat the same way a network-unreachable error is treated.
    """
    try:
        return firebase_client_for(APP_NAME)
    except ConfigError as exc:
        msg = f"home-guard sync not configured: {exc}"
        raise SyncUnavailableError(msg) from exc
    except FirebaseAuthError as exc:
        msg = f"home-guard sync credentials rejected: {exc}"
        raise SyncUnavailableError(msg) from exc
