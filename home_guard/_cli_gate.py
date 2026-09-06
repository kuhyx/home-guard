"""``home_guard gate``: arm the lock if a slot is due. Systemd's entrypoint."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gatelock import wait_for_x_server

from home_guard._cli_output import emit
from home_guard._gate import due_slots
from home_guard._lock import HomeGuardGuard

if TYPE_CHECKING:
    import argparse


def cmd_gate(args: argparse.Namespace) -> int:
    """Check whether any slot is due, and arm the lock if so.

    Waits for the X server first -- a ``Persistent=true`` catch-up run can
    fire before the display manager has finished, which otherwise crashes
    with "no display name and no $DISPLAY" before the window ever opens
    (the exact race diet-guard's own gate service comment documents). A
    timeout here just means this tick gives up; the next scheduled tick
    tries again, so nothing is silently skipped forever.
    """
    now = datetime.now(tz=UTC).astimezone()
    slots = due_slots(now)
    if not slots:
        emit("home-guard: nothing due.")
        return 0
    if not wait_for_x_server():
        emit("home-guard: no X server available; will retry next tick.")
        return 1
    guard = HomeGuardGuard(slot=slots[0], demo_mode=args.demo)
    guard.run()
    return 0


def add_gate_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``gate`` subcommand."""
    parser = subparsers.add_parser(
        "gate", help="check due slots and arm the lock if needed"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="soft/closeable lock for testing, instead of the hard production lock",
    )
    parser.set_defaults(func=cmd_gate)
