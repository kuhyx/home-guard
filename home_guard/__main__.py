"""Entrypoint for ``python -m home_guard``."""

from __future__ import annotations

import sys

from home_guard._cli import main

if (
    __name__ == "__main__"
):  # pragma: no cover -- exercised via `python -m home_guard`, not pytest
    sys.exit(main())
