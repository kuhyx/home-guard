"""Merge two zone-list histories written by two devices with no locking.

The PC and the phone both append to the same forward-only history, so the
merge has to be deterministic and order-independent: whichever side runs it,
on whatever pair of histories, must land on the same result.

Three rules, in order:

1. Union the entries by ``effective_from``.
2. A same-day collision is resolved by ``edited_at`` -- the later edit wins.
   (:func:`home_guard._zone_list.record_zone_list_change` resolves the same
   collision *positionally*, "the one being written wins", which is correct
   for a single writer and wrong for a merge.)
3. A **remote** entry dated before today is dropped, and a local entry for a
   past day is never replaced.

Rule 3 is the one that matters. ``.zone_list`` is forward-only precisely so
that editing the rotation cannot retroactively change which zone an
already-judged past slot was checked against (``docs/DOCS-zone-rotation.md``).
A second writer -- buggy, stale-clocked, or just a phone whose timezone is
wrong -- must not be able to void that invariant, and this preserves it
without having to trust the phone at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from home_guard._zone_list import ZoneListEntry


def _by_day(entries: tuple[ZoneListEntry, ...]) -> dict[str, ZoneListEntry]:
    """Index by ``effective_from``, later ``edited_at`` winning a duplicate.

    A history read off disk should not contain duplicate days, but a remote
    one is whatever another device wrote, so this must not assume it.
    """
    indexed: dict[str, ZoneListEntry] = {}
    for entry in entries:
        existing = indexed.get(entry.effective_from)
        if existing is None or entry.edited_at > existing.edited_at:
            indexed[entry.effective_from] = entry
    return indexed


def merge_histories(
    local: tuple[ZoneListEntry, ...],
    remote: tuple[ZoneListEntry, ...],
    *,
    today: str,
) -> tuple[ZoneListEntry, ...]:
    """Merge ``remote`` into ``local``. Returns the merged history, oldest first.

    Args:
        local: This device's history, authoritative for every past day.
        remote: The other device's history, trusted only from ``today`` on.
        today: ``YYYY-MM-DD`` in **local** time, matching the rest of the repo.

    Returns:
        The merged entries sorted by ``effective_from``.
    """
    merged = _by_day(local)
    for day, entry in _by_day(remote).items():
        if day < today:
            # Rule 3: the past is not the remote writer's to rewrite.
            continue
        existing = merged.get(day)
        if existing is None or entry.edited_at > existing.edited_at:
            merged[day] = entry
    return tuple(sorted(merged.values(), key=lambda e: e.effective_from))
