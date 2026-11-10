"""Widgets for one lock surface: zone name, status icon, escape hatch.

Text-free by kuhy's textgate rule: the only words painted are the zone name
(his own content) and the bypass command (an escape phrase he types). Every
other cue is a drawn icon from ``_icons.py``; ``status_var`` holds an icon
*name* (``wait``/``warn``/``no``), never a sentence.

Pure rendering -- no state beyond the Tk widgets themselves. All app state
(current zone, status icon) lives in ``tk.Variable``s mastered on the root
by ``_lock.py``, per gatelock's own convention that every surface must read
the same state.

``build_surface`` is exercised by ``tests/test_lock_integration.py`` and
``tests/test_lock_no_words.py`` (subprocess tests -- see ``_lock.py``'s note
on why the coverage percentage under-reports this file).
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from gatelock import LockConfig, RowStyle, row

from home_guard import _icons

if TYPE_CHECKING:
    from collections.abc import Callable

# The manual bypass, shown as the bare command: it is something kuhy types,
# so it stays visible (textgate settled decision 2). The sentence around it
# is gone.
BYPASS_COMMAND = "systemctl --user stop home-guard-gate.service"

STATUS_WAIT = "wait"
STATUS_OFFLINE = "warn"
STATUS_REJECTED = "no"


def status_color(config: LockConfig, status: str) -> str:
    """The colour that goes with a status icon name."""
    palette = config.palette
    return {
        STATUS_WAIT: palette.muted,
        STATUS_OFFLINE: palette.warning,
        STATUS_REJECTED: palette.danger,
    }.get(status, palette.muted)


def icon(
    parent: tk.Misc, config: LockConfig, name: str, *, size: int, color: str
) -> tk.Canvas:
    """A ``size``-pixel canvas with icon ``name`` drawn on it (not packed)."""
    canvas = tk.Canvas(
        parent, width=size, height=size, bg=config.palette.bg, highlightthickness=0
    )
    _icons.draw(canvas, name, size=size, color=color)
    return canvas


def icon_button(
    parent: tk.Misc,
    config: LockConfig,
    name: str,
    command: Callable[[], None],
    *,
    color: str,
) -> tk.Canvas:
    """A focusable drawn-icon button: click, Return or space runs ``command``."""
    size = config.type_px("display")
    canvas = tk.Canvas(
        parent,
        width=size,
        height=size,
        bg=config.palette.field_bg,
        takefocus=1,
        cursor="hand2",
        **config.focus_kwargs(),
    )
    _icons.draw(canvas, name, size=size, color=color)
    for sequence in ("<Button-1>", "<Return>", "<space>"):
        canvas.bind(sequence, lambda _e: command())
    return canvas


def _status_icon(
    parent: tk.Misc, config: LockConfig, status_var: tk.StringVar
) -> tk.Canvas:
    size = config.type_px("display")
    canvas = icon(parent, config, STATUS_WAIT, size=size, color=config.palette.muted)

    def _redraw(*_args: object) -> None:
        status = status_var.get()
        canvas.delete("all")
        _icons.draw(canvas, status, size=size, color=status_color(config, status))

    _redraw()
    trace = status_var.trace_add("write", _redraw)
    canvas.bind("<Destroy>", lambda _e: status_var.trace_remove("write", trace))
    return canvas


def build_surface(
    parent: tk.Misc,
    config: LockConfig,
    *,
    zone_var: tk.StringVar,
    status_var: tk.StringVar,
    on_report_trouble: Callable[[], None],
) -> None:
    """Build the widgets shown on one output for the armed lock."""
    # The zone is the one thing to read here, so it gets the display size and
    # the top margin the removed heading used to give.
    zone = row(parent, config, "", style=RowStyle(role="display"))
    zone.config(textvariable=zone_var)
    zone.pack_configure(pady=(config.space("xl"), config.space("sm")))

    # Camera -> phone: "photograph it with the phone app".
    how = tk.Frame(parent, bg=config.palette.bg)
    how.pack(padx=config.space("xl"), pady=config.space("md"), anchor="w")
    size = config.type_px("display")
    for name in ("camera", "arrow", "phone"):
        icon(how, config, name, size=size, color=config.palette.accent).pack(
            side="left", padx=config.space("xs")
        )

    _status_icon(parent, config, status_var).pack(
        padx=config.space("xl"), pady=config.space("md"), anchor="w"
    )
    row(
        parent,
        config,
        BYPASS_COMMAND,
        style=RowStyle(role="caption", color=config.palette.muted),
    )
    icon_button(
        parent, config, "escape", on_report_trouble, color=config.palette.muted
    ).pack(padx=config.space("xl"), pady=config.space("lg"), anchor="w")
