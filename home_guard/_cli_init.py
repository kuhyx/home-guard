"""``home_guard init``: seed the zone rotation, idempotently."""

from __future__ import annotations

from typing import TYPE_CHECKING

from home_guard._cli_output import emit
from home_guard._constants import DEFAULT_ZONES
from home_guard._zone_cursor import seed_default as seed_cursor
from home_guard._zone_list import load_zone_list_entries, record_zone_list_change

if TYPE_CHECKING:
    import argparse

_EPOCH_DAY = "1970-01-01"


def cmd_init(args: argparse.Namespace) -> int:
    """Seed ``.zone_list``/``.zone_cursor`` if not already initialized."""
    existing = load_zone_list_entries()
    if existing:
        emit("home-guard: zone rotation already initialized; leaving it as-is.")
    else:
        zones = tuple(args.zones) if args.zones else DEFAULT_ZONES
        record_zone_list_change(zones, effective_from=_EPOCH_DAY)
        emit(f"home-guard: seeded zone rotation: {', '.join(zones)}")
    seed_cursor()
    return 0


def add_init_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``init`` subcommand."""
    parser = subparsers.add_parser(
        "init", help="seed the zone rotation (safe to re-run)"
    )
    parser.add_argument(
        "--zones",
        nargs="+",
        default=None,
        metavar="ZONE",
        help="initial rotation, e.g. --zones desk 'kitchen counter' entryway",
    )
    parser.set_defaults(func=cmd_init)
