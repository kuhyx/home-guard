"""Choosing the Firebase RTDB client home-guard's sync calls will use.

``ConfigError`` subclasses ``Exception`` directly rather than
``RemoteSyncError`` -- a gotcha diet-guard's own ``_sync_client.py`` flags
explicitly and had bitten that file before. Every caller here catches both
explicitly rather than assuming one covers the other, so an unconfigured
Firebase setup never throws a raw traceback out of a fullscreen lock.

Every client handed out is crdt_sync's encrypting store: payloads under
``SYNC_PREFIX`` are sealed with a key derived (Argon2id) from the shared
crdt-sync passphrase. With no passphrase, or the wrong one, there is no
client at all (:class:`SyncLockedError`), so no caller can ever write
plaintext -- it takes the same "skip, try next tick" path as an outage.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from crdt_sync import (
    PASSWORD_FILE,
    ConfigError,
    E2eLockedError,
    FirebaseAuthError,
    firebase_client_for,
    open_encrypted_client,
)

from home_guard._constants import APP_NAME, E2E_STATE_DIR, SYNC_OLD_PREFIX

if TYPE_CHECKING:
    from crdt_sync import Argon2Params, RemoteStore

_logger = logging.getLogger(__name__)


class SyncUnavailableError(Exception):
    """Raised when no usable Firebase client could be built right now."""


class SyncLockedError(SyncUnavailableError):
    """No usable E2E key on this machine: missing or wrong passphrase."""


# Argon2id cost; None = the library's recommended params. Tests lower it.
ARGON2_PARAMS: Argon2Params | None = None


class _NoLegacyCopy:
    """Delegates to ``inner`` but shows nothing under the old prefix.

    ``open_encrypted_client`` runs a one-time copy of the old prefix's CRDT
    logs. home-guard has none: its nodes are plain JSON transport blobs, so
    the copy can only ever pick up the drained ``{}`` evidence node (which
    parses as an empty log). crdt-sync < 0.11.0 merged that onto a pending
    upload at the new path (a crash here, wiped photos in Dart); 0.11.0
    skips it, so this is now belt and braces plus one scan fewer per open.
    The old data stays where it is, untouched.
    """

    def __init__(self, inner: RemoteStore) -> None:
        self._inner = inner

    def list_directory(self, path: str) -> list[str]:
        if path == SYNC_OLD_PREFIX:
            return []
        return self._inner.list_directory(path)

    def get_file_text(self, path: str) -> str | None:
        return self._inner.get_file_text(path)

    def put_file_text(self, path: str, text: str, *, message: str) -> None:
        self._inner.put_file_text(path, text, message=message)

    def delete_file(self, path: str, *, message: str = "") -> None:
        self._inner.delete_file(path, message=message)

    def can_access_remote(self) -> bool:
        return self._inner.can_access_remote()


def _read_passphrase() -> str:
    """The shared crdt-sync passphrase, or "" when this machine has none."""
    try:
        return PASSWORD_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def get_sync_client() -> RemoteStore:
    """Return a signed-in Firebase client, or raise :class:`SyncUnavailableError`.

    Neither an unconfigured setup nor a rejected credential is a bug in this
    app -- both mean "this machine cannot sync right now", which callers must
    treat the same way a network-unreachable error is treated.
    """
    try:
        client = firebase_client_for(APP_NAME)
    except ConfigError as exc:
        msg = f"home-guard sync not configured: {exc}"
        raise SyncUnavailableError(msg) from exc
    except FirebaseAuthError as exc:
        msg = f"home-guard sync credentials rejected: {exc}"
        raise SyncUnavailableError(msg) from exc
    try:
        store, _layout = open_encrypted_client(
            _NoLegacyCopy(client),
            SYNC_OLD_PREFIX,
            passphrase=_read_passphrase(),
            params=ARGON2_PARAMS,
            state_dir=E2E_STATE_DIR,
        )
    except E2eLockedError as exc:
        _logger.warning("home-guard sync locked, skipping: %s", exc)
        msg = f"home-guard sync locked: {exc}"
        raise SyncLockedError(msg) from exc
    return store
