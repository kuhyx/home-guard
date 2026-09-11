"""Find a node in a ``uiautomator dump`` and report its centre, or its presence.

Used by ``scripts/register_oauth_client.sh`` to read the phone app's screen
back after a sign-in, instead of trusting a local flag. Coordinates are looked
up rather than hardcoded because ``adb shell screencap`` is downscaled on the
target phone: a tap aimed at a screenshot pixel lands at roughly double the
intended ``y``.

The dump is a flat list of ``<node .../>`` tags, so it is read with a regular
expression over attributes rather than an XML parser: the input is this
machine's own ``adb`` output, and pulling in ``defusedxml`` for it would add a
runtime dependency to the systemd path for a helper the gate never runs.

Usage::

    python3 -m home_guard._ui_dump <dump.xml> centre <substring>
    python3 -m home_guard._ui_dump <dump.xml> has <substring>
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Final

from home_guard._cli_output import emit

_NODE: Final = re.compile(r"<node\b([^>]*)>")
_ATTR: Final = re.compile(r'([\w-]+)="([^"]*)"')
_BOUNDS: Final = re.compile(r"\[(\d+),(\d+)]\[(\d+),(\d+)]")

_ARGC: Final = 4
_MODES: Final = ("centre", "has")


def _attrs(dump: str) -> list[dict[str, str]]:
    return [dict(_ATTR.findall(tag)) for tag in _NODE.findall(dump)]


def _matching(dump: str, needle: str) -> list[dict[str, str]]:
    lowered = needle.lower()
    return [
        node
        for node in _attrs(dump)
        if lowered in node.get("text", "").lower()
        or lowered in node.get("content-desc", "").lower()
    ]


def find_centre(dump: str, needle: str) -> tuple[int, int] | None:
    """Return the ``(x, y)`` centre of the first node whose text has ``needle``.

    ``None`` when no node matches, or the match carries no parseable bounds.
    """
    for node in _matching(dump, needle):
        match = _BOUNDS.match(node.get("bounds", ""))
        if match is None:
            continue
        left, top, right, bottom = (int(value) for value in match.groups())
        return (left + right) // 2, (top + bottom) // 2
    return None


def has_text(dump: str, needle: str) -> bool:
    """Whether some node's text or content-desc contains ``needle``."""
    return bool(_matching(dump, needle))


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Exit 0 on a hit, 1 on a miss, 2 on usage or a missing dump."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != _ARGC - 1 or args[1] not in _MODES:
        sys.stderr.write(f"{__doc__}\n")
        return 2
    path = Path(args[0])
    if not path.exists():
        sys.stderr.write(f"no such dump: {path}\n")
        return 2
    dump = path.read_text(encoding="utf-8")
    if args[1] == "has":
        return 0 if has_text(dump, args[2]) else 1
    centre = find_centre(dump, args[2])
    if centre is None:
        return 1
    emit(f"{centre[0]} {centre[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
