"""``home_guard zones``: read and edit the rotation after init.

Fills a real gap. ``record_zone_list_change()`` has existed since the first
draft, but its only non-test caller was ``_cli_init.py``, which refuses to
write once a history exists -- so on an already-initialised machine the only
way to add "mirror" to the rotation was to hand-edit unsigned JSON.

Every edit is an append to the forward-only history with ``effective_from``
defaulting to **today**, never the epoch: an edit must not retroactively
change which zone an already-judged past slot was checked against.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from home_guard._cli_output import emit
from home_guard._sync_zones import fetch_zone_history, publish_zone_history
from home_guard._zone_list import (
    load_zone_list_entries,
    record_zone_list_change,
    write_entries,
    zone_list_for_day,
)
from home_guard._zone_merge import merge_histories

if TYPE_CHECKING:
    import argparse


def _today() -> str:
    """Local date, matching how ``_gate.py`` formats a day."""
    return datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d")


def _pull(today: str) -> str:
    """Merge the published history into the local one. Returns a status note."""
    remote = fetch_zone_history()
    if remote is None:
        return "could not read the published rotation; using the local one."
    local = load_zone_list_entries()
    merged = merge_histories(local, remote, today=today)
    if merged == local:
        return "already up to date with the phone."
    write_entries(merged)
    return "merged edits from the phone."


def _edited_rotation(args: argparse.Namespace, today: str) -> tuple[str, ...] | None:
    """Resolve --set/--add/--remove into the new rotation. ``None`` = refuse.

    ``--add`` is the common case and the verb the rotation is actually edited
    with day to day: you notice a fixture you clean and want it in the cycle,
    without having to retype the ones already there.
    """
    current = zone_list_for_day(load_zone_list_entries(), today)
    if args.set is not None:
        zones = tuple(z.strip() for z in args.set if z.strip())
    else:
        zones = current
        if args.add is not None:
            # Dedupe against the rotation AND against the rest of this call:
            # adding "mirror" twice is a typo, not a request for it to come
            # round twice as often.
            seen = set(zones)
            additions: list[str] = []
            for raw in args.add:
                name = raw.strip()
                if name and name not in seen:
                    seen.add(name)
                    additions.append(name)
            zones = (*zones, *additions)
        if args.remove is not None:
            drop = {z.strip() for z in args.remove if z.strip()}
            missing = drop - set(zones)
            if missing:
                emit(f"home-guard: not in the rotation: {', '.join(sorted(missing))}")
                return None
            zones = tuple(z for z in zones if z not in drop)
    if not zones:
        emit("home-guard: a rotation must have at least one zone.")
        return None
    return zones


def cmd_zones(args: argparse.Namespace) -> int:
    """List the rotation, or replace it with ``--set``."""
    today = _today()

    # Always merge before showing or editing: the phone is a real writer, so
    # printing (or replacing) a rotation without pulling first would report
    # state that is already stale.
    emit(f"home-guard: {_pull(today)}")

    if args.set is not None or args.add is not None or args.remove is not None:
        zones = _edited_rotation(args, today)
        if zones is None:
            return 1
        effective = args.effective_from or today
        if effective < today:
            emit(
                f"home-guard: --effective-from {effective} is in the past; "
                "the rotation is forward-only."
            )
            return 1
        record_zone_list_change(zones, effective_from=effective)
        emit(f"home-guard: rotation from {effective}: {', '.join(zones)}")
        if not publish_zone_history(load_zone_list_entries()):
            emit("home-guard: saved locally, but could not publish to the phone.")
        return 0

    entries = load_zone_list_entries()
    current = zone_list_for_day(entries, today)
    emit(f"home-guard: rotation today ({today}): {', '.join(current)}")
    for entry in entries:
        emit(f"  from {entry.effective_from}: {', '.join(entry.zones)}")
    return 0


def add_zones_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``zones`` subcommand."""
    parser = subparsers.add_parser("zones", help="show or edit the zone rotation")
    parser.add_argument(
        "--set",
        nargs="+",
        default=None,
        metavar="ZONE",
        help="replace the rotation, e.g. --set mirror toilet 'washing machine'",
    )
    parser.add_argument(
        "--add",
        nargs="+",
        default=None,
        metavar="ZONE",
        help="append zones to the rotation, e.g. --add mirror 'washing machine'",
    )
    parser.add_argument(
        "--remove",
        nargs="+",
        default=None,
        metavar="ZONE",
        help="drop zones from the rotation",
    )
    parser.add_argument(
        "--effective-from",
        default=None,
        metavar="YYYY-MM-DD",
        help="the day the new rotation takes effect (default: today)",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="merge the phone's edits without changing anything yourself",
    )
    parser.set_defaults(func=cmd_zones)
