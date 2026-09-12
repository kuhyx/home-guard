"""Tests for publishing and fetching the zone rotation over RTDB."""

from __future__ import annotations

from home_guard._constants import SYNC_ZONES_PATH
from home_guard._sync_zones import fetch_zone_history, publish_zone_history
from home_guard._zone_list import ZoneListEntry
from home_guard.tests.fake_remote_store import FakeRemoteStore

_ENTRIES = (
    ZoneListEntry(
        effective_from="2026-09-12",
        zones=("mirror", "toilet"),
        edited_at="2026-09-12T19:00:00+00:00",
    ),
)


def test_publish_then_fetch_round_trips() -> None:
    client = FakeRemoteStore()
    assert publish_zone_history(_ENTRIES, client=client) is True
    assert fetch_zone_history(client=client) == _ENTRIES


def test_publish_returns_false_on_outage() -> None:
    assert publish_zone_history(_ENTRIES, client=FakeRemoteStore(fail=True)) is False


def test_fetch_returns_none_on_outage() -> None:
    """None, not (): "could not see it" must not read as "it is empty"."""
    assert fetch_zone_history(client=FakeRemoteStore(fail=True)) is None


def test_fetch_returns_none_when_absent() -> None:
    assert fetch_zone_history(client=FakeRemoteStore()) is None


def test_fetch_returns_none_on_empty_string() -> None:
    client = FakeRemoteStore()
    client.put_file_text(SYNC_ZONES_PATH, "")
    assert fetch_zone_history(client=client) is None


def test_fetch_returns_none_on_invalid_json() -> None:
    client = FakeRemoteStore()
    client.put_file_text(SYNC_ZONES_PATH, "{not json")
    assert fetch_zone_history(client=client) is None


def test_fetch_returns_none_on_wrong_shape() -> None:
    client = FakeRemoteStore()
    client.put_file_text(SYNC_ZONES_PATH, '["not", "a", "history"]')
    assert fetch_zone_history(client=client) is None


def test_fetch_returns_empty_tuple_for_an_empty_history() -> None:
    """Distinct from None: the node was readable and said "no edits"."""
    client = FakeRemoteStore()
    client.put_file_text(SYNC_ZONES_PATH, '{"v": 1, "e": {}}')
    assert fetch_zone_history(client=client) == ()
