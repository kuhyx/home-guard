"""Tests for the drawn pictograms and the escape dialog's word-free helpers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from gatelock import EscapeDraft

from home_guard import _icons
from home_guard._escape_dialog import budget_numerals, recent_lines
from home_guard._escape_hatch import build_tracker
from home_guard._view import (
    STATUS_OFFLINE,
    STATUS_REJECTED,
    STATUS_WAIT,
    status_color,
)

if TYPE_CHECKING:
    from pathlib import Path
    import tkinter as tk

    from gatelock import EscapeTracker

_WORD = re.compile(r"[A-Za-z]{2,}")


class _FakeCanvas:
    """Records every create_* call instead of drawing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[float, ...], dict[str, object]]] = []

    def _record(self, kind: str, *pts: float, **kw: object) -> None:
        self.calls.append((kind, pts, kw))

    def create_rectangle(self, *pts: float, **kw: object) -> None:
        self._record("rect", *pts, **kw)

    def create_oval(self, *pts: float, **kw: object) -> None:
        self._record("oval", *pts, **kw)

    def create_polygon(self, *pts: float, **kw: object) -> None:
        self._record("poly", *pts, **kw)

    def create_line(self, *pts: float, **kw: object) -> None:
        self._record("line", *pts, **kw)


def _as_canvas(fake: _FakeCanvas) -> tk.Canvas:
    return cast("tk.Canvas", fake)


def test_every_icon_draws_its_primitives_scaled() -> None:
    for name, prims in _icons.SHAPES.items():
        canvas = _FakeCanvas()
        _icons.draw(_as_canvas(canvas), name, size=48, color="#fff")
        assert [c[0] for c in canvas.calls] == [p[0] for p in prims], name
        for (_, pts, _kw), (_, grid, _filled) in zip(canvas.calls, prims, strict=True):
            assert list(pts) == [g * 2 for g in grid], name


def test_filled_shapes_are_filled_and_outlines_are_not() -> None:
    canvas = _FakeCanvas()
    _icons.draw(_as_canvas(canvas), "camera", size=24, color="#abc")
    fills = [kw["fill"] for _, _, kw in canvas.calls]
    assert fills == ["", "#abc", ""]


def test_every_status_the_lock_uses_has_an_icon_and_a_distinct_colour() -> None:
    from gatelock import LockConfig

    config = LockConfig()
    statuses = (STATUS_WAIT, STATUS_OFFLINE, STATUS_REJECTED)
    assert all(s in _icons.SHAPES for s in statuses)
    colours = {status_color(config, s) for s in statuses}
    assert len(colours) == len(statuses)
    assert status_color(config, "unknown") == config.palette.muted


def _tracker(tmp_path: Path) -> EscapeTracker:
    return build_tracker(
        path=tmp_path / "escape_history.json", key_file=tmp_path / "no-key"
    )


def test_budget_is_numerals_only(tmp_path: Path) -> None:
    tracker = _tracker(tmp_path)
    policy = tracker.policy
    assert budget_numerals(tracker) == (
        f"0/{policy.budget_per_7_days} · 0/{policy.budget_per_30_days} · "
        f"0/{policy.budget_per_90_days}"
    )
    assert not _WORD.search(budget_numerals(tracker))


def test_recent_lines_are_empty_then_show_the_typed_words(tmp_path: Path) -> None:
    tracker = _tracker(tmp_path)
    assert recent_lines(tracker) == []
    tracker.record(
        EscapeDraft(
            reason="router dead", onset="9am", severity=7, description="y" * 45
        ),
        today="2026-09-06",
    )
    (line,) = recent_lines(tracker)
    assert line.startswith("2026-09-06  7/10  router dead: yyy")
