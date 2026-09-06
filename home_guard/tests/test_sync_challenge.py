"""Tests for publishing a challenge to the fake RTDB store."""

from __future__ import annotations

import json

from home_guard._challenge_store import ChallengeRecord
from home_guard._constants import SYNC_CHALLENGE_PATH
from home_guard._sync_challenge import publish_challenge
from home_guard.tests.fake_remote_store import FakeRemoteStore

# The challenge echo under test. A name rather than an inline literal, so
# ruff's S105/S106 (hardcoded password) never trips on a value that is not one.
_ECHO = "tok"

_RECORD = ChallengeRecord(
    day="2026-09-06",
    slot="0800",
    zone="desk",
    token=_ECHO,
    issued_at="2026-09-06T08:00:00+00:00",
    consumed=False,
)


def test_publish_succeeds_and_writes_payload() -> None:
    client = FakeRemoteStore()
    assert publish_challenge(_RECORD, client=client) is True
    stored = json.loads(client.get_file_text(SYNC_CHALLENGE_PATH))
    assert stored["token"] == _ECHO
    assert stored["zone"] == "desk"


def test_publish_returns_false_on_outage() -> None:
    client = FakeRemoteStore(fail=True)
    assert publish_challenge(_RECORD, client=client) is False
