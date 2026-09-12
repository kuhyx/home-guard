"""Best-effort mint-and-publish of a due slot's challenge.

**Arming never depends on the network.** ``_gate.py``'s due-check is pure
local date/log arithmetic, and the lock always arms when due, full stop --
an offline machine still gets locked, exactly like every sibling gate. What
*does* depend on the network is only how the user can prove they cleared the
zone: this module mints the challenge and tries to publish it, and reports
whether that worked so the lock UI can show accurate status (and, on
failure, offer the bounded escape hatch in ``_escape_hatch.py`` -- never a
silent, unbounded free pass).

An earlier version of this module skipped arming entirely and logged a
zero-effort "incident" the moment Firebase merely looked unreachable. That
was an unbounded exploit (block ``firebaseio.com`` forever, tidy never
again) and has been removed; see ``_log.py``'s module docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from home_guard._challenge import mint_challenge
from home_guard._netcheck import Reachability, classify_reachability
from home_guard._paths import resolve_paths
from home_guard._sync_challenge import publish_challenge
from home_guard._zone_cursor import current_zone

if TYPE_CHECKING:
    from datetime import datetime

    from home_guard._challenge_store import ChallengeRecord
    from home_guard._paths import HomeGuardPaths

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublishAttempt:
    """The outcome of trying to make this slot's challenge reachable."""

    zone: str
    challenge: ChallengeRecord
    published: bool
    reachability: Reachability | None
    """Only computed (non-None) when ``published`` is False."""


def prepare_slot(
    now: datetime,
    slot: str,
    *,
    paths: HomeGuardPaths | None = None,
) -> PublishAttempt:
    """Mint (idempotently) and attempt to publish this slot's challenge.

    Never blocks arming: the caller arms the lock regardless of the result,
    and uses ``published``/``reachability`` only to decide what to show.
    """
    resolved = resolve_paths(paths)
    day = now.strftime("%Y-%m-%d")
    zone = current_zone(now, paths=resolved)
    record = mint_challenge(
        day=day,
        slot=slot,
        zone=zone,
        now=now,
        paths=resolved,
    )
    if publish_challenge(record):
        return PublishAttempt(
            zone=zone, challenge=record, published=True, reachability=None
        )
    reachability = classify_reachability()
    _logger.warning(
        "home-guard could not publish the challenge for slot %s (%s)",
        slot,
        reachability,
    )
    return PublishAttempt(
        zone=zone, challenge=record, published=False, reachability=reachability
    )
