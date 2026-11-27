"""``home_guard history``: print recent clear/escape log entries, read-only."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from home_guard._cli_output import emit
from home_guard._log import recent_entries

if TYPE_CHECKING:
    import argparse


def cmd_history(args: argparse.Namespace) -> int:
    """Print recent clear/escape log entries, newest first."""
    entries = recent_entries(limit=args.limit)
    if not entries:
        emit("home-guard: no clears or escapes logged yet.")
        return 0
    for entry in entries:
        emit(json.dumps(entry, sort_keys=True))
    return 0


def add_history_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``history`` subcommand."""
    parser = subparsers.add_parser(
        "history", help="print recent clear/escape log entries, read-only"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="how many entries, newest first",
    )
    parser.set_defaults(func=cmd_history)
