"""Top-level ``home_guard`` CLI: dispatch to init/gate/status/zones."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from home_guard._cli_gate import add_gate_parser
from home_guard._cli_init import add_init_parser
from home_guard._cli_status import add_status_parser
from home_guard._cli_zones import add_zones_parser

if TYPE_CHECKING:
    from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with every subcommand registered."""
    parser = argparse.ArgumentParser(prog="home_guard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_init_parser(subparsers)
    add_gate_parser(subparsers)
    add_status_parser(subparsers)
    add_zones_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and dispatch to the selected subcommand."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
