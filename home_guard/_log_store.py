"""Atomic read/write of the append-only clear log file.

Split out from ``_log.py`` for file-size and to keep the raw-disk shape
separate from the sign/verify/append business logic. Mirrors diet-guard's
``_state.py`` read/write pair.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from home_guard._constants import CLEAR_LOG_FILE

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)


def read_raw_log(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Read the full ``{day: [entry, ...]}`` log. Missing/corrupt -> empty."""
    target = path if path is not None else CLEAR_LOG_FILE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        _logger.warning("could not read clear log %s: %s", target, exc)
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for day, entries in raw.items():
        if isinstance(day, str) and isinstance(entries, list):
            result[day] = [e for e in entries if isinstance(e, dict)]
    return result


def write_log(log: dict[str, list[dict[str, Any]]], path: Path | None = None) -> None:
    """Atomically replace the log file's contents (temp-file + ``os.replace``)."""
    target = path if path is not None else CLEAR_LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(log, indent=2), encoding="utf-8")
    tmp.replace(target)


def append_entry(
    entry: dict[str, Any],
    day: str,
    path: Path | None = None,
) -> None:
    """Append ``entry`` under ``day`` and persist. Never rewrites past entries."""
    target = path if path is not None else CLEAR_LOG_FILE
    log = read_raw_log(target)
    log.setdefault(day, []).append(entry)
    write_log(log, target)
