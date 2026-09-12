"""Tests for merging two devices' zone-list histories."""

from __future__ import annotations

from home_guard._zone_list import ZoneListEntry
from home_guard._zone_merge import merge_histories

TODAY = "2026-09-12"


def _e(day: str, zones: tuple[str, ...], t: str) -> ZoneListEntry:
    return ZoneListEntry(effective_from=day, zones=zones, edited_at=t)


def test_disjoint_days_are_unioned() -> None:
    local = (_e("2026-09-12", ("desk",), "2026-09-12T08:00:00+00:00"),)
    remote = (_e("2026-09-13", ("mirror",), "2026-09-12T09:00:00+00:00"),)
    merged = merge_histories(local, remote, today=TODAY)
    assert [e.effective_from for e in merged] == ["2026-09-12", "2026-09-13"]


def test_merge_is_order_independent() -> None:
    """Either device running the merge must land on the same history."""
    a = (_e("2026-09-12", ("desk",), "2026-09-12T08:00:00+00:00"),)
    b = (_e("2026-09-13", ("mirror",), "2026-09-12T09:00:00+00:00"),)
    assert merge_histories(a, b, today=TODAY) == merge_histories(b, a, today=TODAY)


def test_same_day_collision_is_won_by_the_later_edit() -> None:
    local = (_e(TODAY, ("desk",), "2026-09-12T08:00:00+00:00"),)
    remote = (_e(TODAY, ("mirror", "toilet"), "2026-09-12T19:30:00+00:00"),)
    merged = merge_histories(local, remote, today=TODAY)
    assert merged[0].zones == ("mirror", "toilet")


def test_local_wins_a_same_day_collision_when_it_is_newer() -> None:
    local = (_e(TODAY, ("desk",), "2026-09-12T20:00:00+00:00"),)
    remote = (_e(TODAY, ("mirror",), "2026-09-12T09:00:00+00:00"),)
    assert merge_histories(local, remote, today=TODAY)[0].zones == ("desk",)


def test_remote_cannot_rewrite_the_past() -> None:
    """The invariant .zone_list exists for: past slots stay judged as judged."""
    local = (_e("2026-09-01", ("desk",), "2026-09-01T08:00:00+00:00"),)
    # A stale-clocked or hostile phone tries to replace a past day, with a
    # newer edited_at so a naive "later wins" would accept it.
    remote = (_e("2026-09-01", ("mirror",), "2099-01-01T00:00:00+00:00"),)
    merged = merge_histories(local, remote, today=TODAY)
    assert merged == local


def test_remote_entry_for_today_is_accepted() -> None:
    local = ()
    remote = (_e(TODAY, ("mirror",), "2026-09-12T09:00:00+00:00"),)
    assert merge_histories(local, remote, today=TODAY) == remote


def test_duplicate_days_within_one_history_collapse_to_the_later() -> None:
    """A remote history is whatever another device wrote; do not assume it is clean."""
    remote = (
        _e(TODAY, ("old",), "2026-09-12T08:00:00+00:00"),
        _e(TODAY, ("new",), "2026-09-12T18:00:00+00:00"),
    )
    merged = merge_histories((), remote, today=TODAY)
    assert len(merged) == 1
    assert merged[0].zones == ("new",)


def test_a_fresh_device_learns_past_entries_it_does_not_have() -> None:
    """Filling a gap is not a rewrite.

    Rejecting every past remote entry looks safer and is wrong: a freshly
    installed phone starts empty and would be permanently unable to learn the
    PC's history.
    """
    remote = (_e("2026-09-01", ("old",), "2026-09-01T08:00:00+00:00"),)
    assert merge_histories((), remote, today=TODAY) == remote


def test_a_past_gap_is_filled_without_touching_existing_past_entries() -> None:
    local = (_e("2026-09-05", ("kept",), "2026-09-05T08:00:00+00:00"),)
    remote = (
        _e("2026-09-01", ("learned",), "2026-09-01T08:00:00+00:00"),
        _e("2026-09-05", ("attempted-rewrite",), "2099-01-01T00:00:00+00:00"),
    )
    merged = merge_histories(local, remote, today=TODAY)
    assert [(e.effective_from, e.zones) for e in merged] == [
        ("2026-09-01", ("learned",)),
        ("2026-09-05", ("kept",)),
    ]


def test_empty_inputs_merge_to_empty() -> None:
    assert merge_histories((), (), today=TODAY) == ()
