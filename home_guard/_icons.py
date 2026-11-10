"""Pictograms for the lock window and escape dialog, drawn on a Tk canvas.

kuhy's textgate rule: the lock shows no words, so every cue is a drawing.
Drawn rather than font glyphs because Tk 8.6 on X11 can crash on colour
emoji, and the symbol fallbacks differ per machine (tofu on a box without
Noto Symbols). Each icon is data on a 24x24 grid, so scaling is one
multiply and a test can check every name has a drawing. Shapes follow
book-guard's ``_icons.py`` so the sibling gates read alike.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import tkinter as tk

Prim = tuple[str, tuple[int, ...], bool]
"""(kind, grid coordinates, filled): kind is rect, oval, line or poly."""

GRID: Final = 24

SHAPES: Final[dict[str, tuple[Prim, ...]]] = {
    "camera": (
        ("rect", (2, 7, 22, 20), False),
        ("rect", (8, 4, 16, 7), True),
        ("oval", (8, 9, 16, 17), False),
    ),
    "phone": (
        ("rect", (7, 2, 17, 22), False),
        ("line", (10, 19, 14, 19), False),
    ),
    "arrow": (
        ("line", (3, 12, 20, 12), False),
        ("line", (15, 7, 20, 12, 15, 17), False),
    ),
    # Hourglass: waiting for the phone's photo.
    "wait": (
        ("line", (5, 3, 19, 3), False),
        ("line", (5, 21, 19, 21), False),
        ("poly", (7, 4, 17, 4, 12, 12), True),
        ("poly", (12, 12, 17, 20, 7, 20), False),
    ),
    "warn": (
        ("poly", (12, 3, 22, 21, 2, 21), False),
        ("line", (12, 9, 12, 15), False),
        ("oval", (11, 17, 13, 19), True),
    ),
    "no": (("line", (5, 5, 19, 19), False), ("line", (19, 5, 5, 19), False)),
    "ok": (("line", (4, 13, 10, 19, 21, 6), False),),
    "clock": (
        ("oval", (3, 3, 21, 21), False),
        ("line", (12, 7, 12, 12, 16, 14), False),
    ),
    # Three rising bars: how bad it is.
    "severity": (
        ("rect", (3, 15, 7, 21), True),
        ("rect", (10, 10, 14, 21), True),
        ("rect", (17, 4, 21, 21), True),
    ),
    "pencil": (
        ("poly", (4, 20, 5, 15, 16, 4, 20, 8, 9, 19), False),
        ("line", (14, 6, 18, 10), False),
    ),
    "escape": (
        ("rect", (3, 3, 13, 21), False),
        ("line", (9, 12, 22, 12), False),
        ("line", (18, 8, 22, 12, 18, 16), False),
    ),
}


def draw(canvas: tk.Canvas, name: str, *, size: int, color: str) -> None:
    """Paint icon ``name`` filling a ``size``-pixel square canvas."""
    k = size / GRID
    width = max(2, round(size / 10))
    for kind, coords, filled in SHAPES[name]:
        pts = [c * k for c in coords]
        fill = color if filled else ""
        if kind == "rect":
            canvas.create_rectangle(*pts, outline=color, fill=fill, width=width)
        elif kind == "oval":
            canvas.create_oval(*pts, outline=color, fill=fill, width=width)
        elif kind == "poly":
            canvas.create_polygon(*pts, outline=color, fill=fill, width=width)
        else:
            canvas.create_line(*pts, fill=color, width=width, capstyle="round")
