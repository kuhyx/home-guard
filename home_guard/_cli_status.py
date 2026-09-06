"""``home_guard status``: print the current gate state without arming anything."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from home_guard._cli_output import emit
from home_guard._gate import due_slots, gate_message

if TYPE_CHECKING:
    import argparse


def cmd_status(_args: argparse.Namespace) -> int:
    """Print whether the gate is due, and for which zone."""
    now = datetime.now(tz=UTC).astimezone()
    slots = due_slots(now)
    emit(gate_message(now))
    if slots:
        emit(f"due slots today: {', '.join(slots)}")
    else:
        emit("nothing due right now.")
    return 0


def add_status_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``status`` subcommand."""
    parser = subparsers.add_parser("status", help="print gate status, read-only")
    parser.set_defaults(func=cmd_status)
