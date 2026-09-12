"""Bundles every overridable on-disk/HMAC-key path in one place.

Every module that touches disk already accepts its own path/key-file
overrides (see ``_gate.py``, ``_accept.py``, ``_escape_hatch.py``,
``_network_incident.py``). This dataclass is just the single object
``_lock.py`` threads through all of them, so constructing a
``HomeGuardGuard`` against a ``tmp_path``-rooted :class:`HomeGuardPaths`
means nothing it does can touch real user state -- the same guarantee
every other module's tests already rely on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class HomeGuardPaths:
    """``None`` for any field means "use the real on-disk default"."""

    challenge_path: Path | None = None
    challenge_key_file: Path | None = None
    log_path: Path | None = None
    log_key_file: Path | None = None
    photos_dir: Path | None = None
    zone_cursor_path: Path | None = None
    zone_list_path: Path | None = None
    escape_history_path: Path | None = None
    escape_key_file: Path | None = None
    disarm_marker_path: Path | None = None


def resolve_paths(paths: HomeGuardPaths | None) -> HomeGuardPaths:
    """Return ``paths`` unchanged, or an all-defaults instance if ``None``.

    The single place every ``paths: HomeGuardPaths | None = None`` parameter
    resolves through, so the "use real defaults" fallback is written once
    instead of repeated at every call site that bundles its path arguments.
    """
    return paths if paths is not None else HomeGuardPaths()
