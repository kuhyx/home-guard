"""Classify a sync failure as a remote outage or this machine's own fault.

The distinction matters because the two deserve opposite treatment: a remote
outage is nobody's fault and must never cost the user anything, while a dead
local network means nothing would work anyway and the check should just be
retried on the next scheduled tick.
"""

from __future__ import annotations

import logging
import socket
from typing import Final, Literal

_logger = logging.getLogger(__name__)

Reachability = Literal["ok", "remote_unreachable", "local_unreachable"]

# A well-known, extremely stable host to distinguish "this machine has no
# internet at all" from "Firebase specifically is down". Deliberately not a
# Google/Firebase host -- that would conflate the two failure modes we are
# trying to tell apart.
_GENERAL_INTERNET_HOST: Final = "1.1.1.1"
_GENERAL_INTERNET_PORT: Final = 443
_FIREBASE_HOST: Final = "firebaseio.com"
_FIREBASE_PORT: Final = 443
_TIMEOUT_SECONDS: Final = 3.0


def _can_connect(host: str, port: int, *, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def classify_reachability(
    *,
    check_general_internet: object = None,
    check_firebase: object = None,
    timeout: float = _TIMEOUT_SECONDS,
) -> Reachability:
    """Return which side of the connection is actually broken.

    Args:
        check_general_internet: Injected replacement for the general-internet
            probe, for tests. ``None`` uses the real network check.
        check_firebase: Injected replacement for the Firebase-reachability
            probe, for tests. ``None`` uses the real network check.
        timeout: Per-probe socket timeout in seconds.
    """
    general_probe = (
        check_general_internet
        if callable(check_general_internet)
        else lambda: _can_connect(
            _GENERAL_INTERNET_HOST, _GENERAL_INTERNET_PORT, timeout=timeout
        )
    )
    firebase_probe = (
        check_firebase
        if callable(check_firebase)
        else lambda: _can_connect(_FIREBASE_HOST, _FIREBASE_PORT, timeout=timeout)
    )
    if firebase_probe():
        return "ok"
    if general_probe():
        return "remote_unreachable"
    return "local_unreachable"
