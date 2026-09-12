"""The disarm marker: an explicit, indefinite "this gate must not lock".

The other half of this contract is ``scripts/disarm_guard.sh``. Three layers
stand between a disarmed machine and a lock, because each alone is defeatable:
masking the units stops systemd, the marker stops ``install.sh`` from copying
fresh unit files over the mask symlinks, and this module stops a hand-run
``python -m home_guard gate``.

Deliberately distinct from the two bounded mechanisms already in the repo.
``freedays`` is a budgeted 35-per-year shared pool for taking a day off, and
``_escape_hatch`` is a justified, rate-limited way past a single slot. Neither
expresses "the app is being rebuilt, do not enforce anything until I say so",
which is an operator decision with no budget to spend and nothing to justify.
It grants no slot and writes no log entry: a disarmed gate never runs, so
there is nothing to excuse -- which is exactly why this is not a third
:mod:`home_guard._log` entry kind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from home_guard._constants import DISARM_MARKER_FILE

if TYPE_CHECKING:
    from pathlib import Path


def _target(marker_path: Path | None) -> Path:
    return marker_path if marker_path is not None else DISARM_MARKER_FILE


def is_disarmed(marker_path: Path | None = None) -> bool:
    """Whether the marker exists.

    Deliberately nothing but an existence check. There is no ``except`` here
    that could land on ``True``: a disable that switches *itself* on because
    of a transient filesystem error would be a worse bug than the enforcement
    it suppresses. ``Path.is_file()`` already answers ``False`` rather than
    raising when the directory is unreadable, so the failure direction is
    "keep enforcing", which is the safe one.
    """
    return _target(marker_path).is_file()


def disarm_reason(marker_path: Path | None = None) -> str:
    """The marker's body text, or a generic line when it is empty/unreadable.

    Never raises: this is only ever used to decorate a message the user is
    already being shown, so an unreadable marker must not turn a clean
    "not arming" into a traceback.
    """
    target = _target(marker_path)
    try:
        text = target.read_text(encoding="utf-8").strip()
    except OSError:
        return "no reason recorded"
    return text or "no reason recorded"
