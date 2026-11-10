"""The sync-trouble escape dialog, drawn without words (textgate rule).

Fields are marked by icons (warning = what is wrong, clock = since when,
bars = severity, pencil = describe it), the budget is bare numerals
(used/allowed per 7, 30 and 90 days), and past justifications are kuhy's own
typed content, so they stay. A refused submit never pops a sentence: the
offending fields get a red outline, a red cross appears, and the
reason goes to the log. The description shows a live ``written/minimum``
counter so the length rule is visible before the submit.

Logic (validation, budget check, log write) lives in ``_escape_hatch.py``,
which is fully covered; this file is exercised by the subprocess test
``tests/test_lock_no_words.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import tkinter as tk
from typing import TYPE_CHECKING

from gatelock import EscapeDraft, EscapeTracker, LockConfig, RowStyle, row

from home_guard import _icons
from home_guard._escape_hatch import SlotZone, grant_escape
from home_guard._view import icon, icon_button

if TYPE_CHECKING:
    from collections.abc import Callable

    from home_guard._paths import HomeGuardPaths

_logger = logging.getLogger(__name__)

# Window title only (an OS-level name, like the app name): never painted
# inside the dialog.
_DIALOG_TITLE = "home-guard"


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


def budget_numerals(tracker: EscapeTracker) -> str:
    """Used/allowed for the 7-, 30- and 90-day windows, numerals only."""
    policy = tracker.policy
    return " · ".join(
        f"{tracker.count_in_window(days)}/{limit}"
        for days, limit in (
            (7, policy.budget_per_7_days),
            (30, policy.budget_per_30_days),
            (90, policy.budget_per_90_days),
        )
    )


def recent_lines(tracker: EscapeTracker) -> list[str]:
    """Past justifications: date, severity and kuhy's own typed words."""
    return [
        f"{entry.get('date', '?')}  {entry.get('severity', '?')}/10  "
        f"{entry.get('reason', '')}: {entry.get('description', '')[:120]}"
        for entry in tracker.recent_justifications()
    ]


def _marked(parent: tk.Misc, config: LockConfig, name: str) -> tk.Frame:
    """A row holding the field icon ``name``; the caller packs the field in."""
    frame = tk.Frame(parent, bg=config.palette.bg)
    frame.pack(fill="x", padx=config.space("xl"), pady=config.space("xs"))
    size = config.type_px("title")
    icon(frame, config, name, size=size, color=config.palette.muted).pack(
        side="left", padx=(0, config.space("sm"))
    )
    return frame


def _flag(widget: tk.Widget, config: LockConfig, *, bad: bool) -> None:
    color = (
        config.palette.danger if bad else config.focus_kwargs()["highlightbackground"]
    )
    widget.configure(highlightbackground=color, highlightthickness=2)


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
    dialog.title(_DIALOG_TITLE)
    dialog.configure(bg=config.palette.bg)
    head = tk.Frame(dialog, bg=config.palette.bg)
    head.pack(fill="x", padx=config.space("xl"), pady=config.space("md"))
    size = config.type_px("display")
    icon(head, config, "escape", size=size, color=config.palette.accent).pack(
        side="left"
    )
    result = icon(head, config, "no", size=size, color=config.palette.bg)
    result.pack(side="right")
    row(
        dialog,
        config,
        budget_numerals(tracker),
        style=RowStyle(color=config.palette.muted),
    )
    for line in recent_lines(tracker):
        row(dialog, config, line, style=RowStyle(role="caption"))

    reason_var = tk.StringVar(dialog)
    onset_var = tk.StringVar(dialog)
    severity_var = tk.IntVar(dialog, value=5)
    entries: dict[str, tk.Entry] = {}
    for name, var in (("warn", reason_var), ("clock", onset_var)):
        entry = tk.Entry(
            _marked(dialog, config, name), textvariable=var, **config.focus_kwargs()
        )
        entry.pack(side="left", fill="x", expand=True)
        entries[name] = entry

    tk.Scale(
        _marked(dialog, config, "severity"),
        from_=1,
        to=10,
        orient="horizontal",
        variable=severity_var,
    ).pack(side="left", fill="x", expand=True)

    minimum = tracker.policy.justification_min_chars
    counter_var = tk.StringVar(dialog, value=f"0/{minimum}")
    described = _marked(dialog, config, "pencil")
    description_text = tk.Text(described, height=4, width=48, **config.focus_kwargs())
    description_text.pack(side="left", fill="x", expand=True)
    counter = row(dialog, config, "", style=RowStyle(role="caption"))
    counter.config(textvariable=counter_var)

    def _count(_event: object = None) -> None:
        written = len(description_text.get("1.0", "end").strip())
        counter_var.set(f"{written}/{minimum}")
        counter.config(
            fg=config.palette.success if written >= minimum else config.palette.muted
        )

    description_text.bind("<KeyRelease>", _count)

    def _submit() -> None:
        draft = EscapeDraft(
            reason=reason_var.get(),
            onset=onset_var.get(),
            severity=severity_var.get(),
            description=description_text.get("1.0", "end"),
        )
        error = grant_escape(tracker, draft, context.target, paths=context.paths)
        if error is not None:
            _logger.info("home-guard escape refused: %s", error)
            _flag(entries["warn"], config, bad=not draft.reason.strip())
            _flag(entries["clock"], config, bad=not draft.onset.strip())
            short = len(draft.description.strip()) < minimum
            _flag(description_text, config, bad=short)
            result.delete("all")
            _icons.draw(result, "no", size=size, color=config.palette.danger)
            return
        dialog.destroy()
        on_granted()

    icon_button(dialog, config, "ok", _submit, color=config.palette.accent).pack(
        padx=config.space("xl"), pady=config.space("lg")
    )
    dialog.grab_set()
