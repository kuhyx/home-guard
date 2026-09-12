"""A bounded, justified way past a slot the automatic path cannot verify.

Wraps ``gatelock.EscapePolicy``/``EscapeTracker`` -- the same "sick mode"
mechanism screen-locker's workout gate uses -- with home-guard's own policy
and history file. A genuine sync outage is real and should not trap the
user forever, but the way past it must be rate-limited, escalating, and
written down, never silent and never unlimited: that budget is what stops
"block firebaseio.com" from being a permanent exploit.

Granting a use of the hatch satisfies *this slot* (the lock releases and
today's check is logged as done) but never rotates the zone -- the zone was
never actually verified clear, so it stays assigned and still due.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from gatelock import EscapeDraft, EscapePolicy, EscapeTracker

from home_guard._constants import ESCAPE_HATCH_HISTORY_FILE, HMAC_KEY_FILE
from home_guard._log import EscapeEntryData, append_escape_entry
from home_guard._paths import resolve_paths

if TYPE_CHECKING:
    from pathlib import Path

    from home_guard._paths import HomeGuardPaths

HATCH_POLICY: Final = EscapePolicy(
    name="home_guard_sync",
    label="sync unavailable",
    budget_per_7_days=2,
    budget_per_30_days=5,
    budget_per_90_days=12,
    lockout_seconds=60,
    lockout_multiplier_per_recent=2,
    justification_min_chars=40,
    history_review_count=5,
)


@dataclass(frozen=True)
class SlotZone:
    """Which due slot and zone one escape-hatch grant applies to."""

    slot: str
    zone: str


def build_tracker(
    *,
    path: Path | None = None,
    key_file: Path | None = None,
) -> EscapeTracker:
    """Return a tracker bound to home-guard's own policy and history file."""
    tracker = EscapeTracker(
        HATCH_POLICY,
        path if path is not None else ESCAPE_HATCH_HISTORY_FILE,
        key_file=key_file if key_file is not None else HMAC_KEY_FILE,
    )
    tracker.load()
    return tracker


def grant_escape(
    tracker: EscapeTracker,
    draft: EscapeDraft,
    target: SlotZone,
    *,
    now: datetime | None = None,
    paths: HomeGuardPaths | None = None,
) -> str | None:
    """Validate, record, and grant one use of the hatch for ``target``'s slot.

    Returns a user-facing complaint if the hatch cannot be used right now
    (budget exhausted, invalid draft, or the history could not be saved), or
    ``None`` on success.
    """
    # Local, never UTC. _gate.py derives its day with .astimezone(), and the
    # log buckets by whatever datetime it is handed, so a UTC-derived day
    # files a post-local-midnight grant under yesterday -- where nothing that
    # grants a slot ever reads. Latent only because the enforcement window
    # keeps the two dates equal for most of the day.
    reference = (now if now is not None else datetime.now(tz=UTC)).astimezone()
    today = reference.strftime("%Y-%m-%d")
    # Same clock for the budget check as for the record: an earlier draft
    # checked the windows against the real calendar while recording under
    # ``now``, so the budget silently reopened as soon as the tests' fixed
    # dates aged out of the 7-day window (CI red from 2026-09-06 on).
    if tracker.is_budget_exhausted(today=today):
        return "No uses of the sync-outage hatch left in any window right now."
    complaint = tracker.validate(draft)
    if complaint is not None:
        return complaint
    if not tracker.record(draft, today=today):
        return "Could not save the escape record -- try again."
    resolved = resolve_paths(paths)
    append_escape_entry(
        EscapeEntryData(slot=target.slot, zone=target.zone, reason=draft.reason),
        now=reference,
        key_file=resolved.log_key_file,
        log_path=resolved.log_path,
    )
    return None
