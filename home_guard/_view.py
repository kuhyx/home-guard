"""Widgets for one lock surface: zone message, status line, escape hatch.

Pure rendering -- no state beyond the Tk widgets themselves. All app state
(current zone, status text, whether a challenge published) lives in
``tk.Variable``s mastered on the root by ``_lock.py``, per gatelock's own
convention that every surface must read the same state.

``build_surface`` is exercised by ``tests/test_lock_integration.py`` (a
subprocess test -- see ``_lock.py``'s note on why the coverage percentage
under-reports this file). ``open_escape_dialog`` is not yet covered by an
automated test; its logic (validation, budget check, log write) lives in
``_escape_hatch.py``, which is fully covered.
"""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

from gatelock import (
    ButtonStyle,
    EscapeDraft,
    EscapeTracker,
    LockConfig,
    RowStyle,
    heading,
    make_button,
    row,
)

from home_guard._escape_hatch import SlotZone, grant_escape

if TYPE_CHECKING:
    from collections.abc import Callable

    from home_guard._paths import HomeGuardPaths


_ESCAPE_HATCH_TITLE = "Report sync trouble"


def build_surface(
    parent: tk.Misc,
    config: LockConfig,
    *,
    zone_var: tk.StringVar,
    status_var: tk.StringVar,
    on_report_trouble: Callable[[], None],
) -> None:
    """Build the widgets shown on one output for the armed lock."""
    heading(parent, config, "home-guard")
    row(parent, config, "", style=RowStyle(role="title")).config(textvariable=zone_var)
    row(
        parent,
        config,
        "Take a photo in the home-guard phone app once it's cleared.",
    )
    row(parent, config, "", style=RowStyle(color=config.muted)).config(
        textvariable=status_var
    )
    row(
        parent,
        config,
        "VT switching is disabled while this is up. To bypass without "
        "clearing anything: systemctl --user stop home-guard-gate.service",
        style=RowStyle(role="caption", color=config.muted),
    )
    button = make_button(
        parent,
        config,
        _ESCAPE_HATCH_TITLE,
        on_report_trouble,
        style=ButtonStyle(variant="secondary", bold=False),
    )
    button.pack(padx=config.space("xl"), pady=config.space("lg"), anchor="w")


@dataclass(frozen=True)
class EscapeDialogContext:
    """Everything ``open_escape_dialog`` needs beyond the Tk parent/config.

    Bundled together because ``tracker``/``target``/``paths`` are all facts
    about *this one escape attempt*, as opposed to ``parent``/``config``
    (Tk plumbing) and ``on_granted`` (the caller's own close callback).
    """

    tracker: EscapeTracker
    target: SlotZone
    paths: HomeGuardPaths | None = None


def open_escape_dialog(
    parent: tk.Misc,
    config: LockConfig,
    *,
    context: EscapeDialogContext,
    on_granted: Callable[[], None],
) -> None:
    """Open a justification form; grant the hatch and call ``on_granted`` on success."""
    tracker = context.tracker
    dialog = tk.Toplevel(parent)
    dialog.title(_ESCAPE_HATCH_TITLE)
    dialog.configure(bg=config.bg)
    heading(dialog, config, _ESCAPE_HATCH_TITLE)
    row(
        dialog,
        config,
        f"Budget: {tracker.budget_summary()}",
        style=RowStyle(color=config.muted),
    )
    row(dialog, config, tracker.format_recent(), style=RowStyle(role="caption"))

    reason_var = tk.StringVar()
    onset_var = tk.StringVar()
    severity_var = tk.IntVar(value=5)
    description_text = tk.Text(dialog, height=4, width=48, **config.focus_kwargs())

    for label, var in (("What's wrong?", reason_var), ("Since when?", onset_var)):
        row(dialog, config, label)
        entry = tk.Entry(dialog, textvariable=var, **config.focus_kwargs())
        entry.pack(fill="x", padx=config.space("xl"))

    row(dialog, config, "Severity (1-10)")
    tk.Scale(dialog, from_=1, to=10, orient="horizontal", variable=severity_var).pack(
        fill="x", padx=config.space("xl")
    )

    row(dialog, config, "Describe it properly:")
    description_text.pack(fill="x", padx=config.space("xl"))

    def _submit() -> None:
        draft = EscapeDraft(
            reason=reason_var.get(),
            onset=onset_var.get(),
            severity=severity_var.get(),
            description=description_text.get("1.0", "end"),
        )
        error = grant_escape(
            tracker,
            draft,
            context.target,
            paths=context.paths,
        )
        if error is not None:
            messagebox.showerror(_ESCAPE_HATCH_TITLE, error, parent=dialog)
            return
        dialog.destroy()
        on_granted()

    make_button(dialog, config, "Submit", _submit).pack(
        padx=config.space("xl"), pady=config.space("lg")
    )
    dialog.grab_set()
