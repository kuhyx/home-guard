"""The one stdout sink every ``home_guard`` subcommand writes through."""

from __future__ import annotations

import sys


def emit(text: str = "") -> None:
    """Write one line to stdout.

    A thin wrapper over ``sys.stdout.write`` (diet-guard's ``_cli._emit``
    shape) so genuine CLI output does not trip ruff's ``T201`` without a
    suppression. Kept deliberately trivial: ``T201`` is *auto-fixable*, and
    an unsafe fix deletes the whole ``print`` call, output and all -- which
    has already happened once in this repo (see ``AGENTS.md``).
    """
    sys.stdout.write(f"{text}\n")
