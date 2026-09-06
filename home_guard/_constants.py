"""Shared literals: rank, paths, cadence, and cap constants.

Single source of truth so no module has to know a magic path or number that
lives somewhere else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

# Arbitration rank. A bare int in THIS module rather than added to
# gatelock._arbiter, same reasoning leetcode_guard's RANK_LEETCODE_GUARD
# uses: a number only home-guard needs shouldn't force a version bump/re-pin
# across the other three live gatelock consumers. Ladder: wake-alarm 300 ->
# screen-locker 200 -> leetcode-guard 150 -> diet-guard 100 -> home-guard 50.
# Tidying is the least time-critical of the five (it costs no sleep, health,
# or income the way the others do), so it always stands down via
# gatelock.wait_for_turn() when a higher-ranked gate is also due, and 50 (not
# 90) leaves headroom below diet-guard for a future gate to slot in between.
RANK_HOME_GUARD: Final = 50

APP_NAME: Final = "home_guard"

# XDG state directory. Never $HOME/.home_guard -- keeps state out of the
# home directory tree that the gate is, ironically, trying to keep tidy.
DATA_DIR: Final = Path.home() / ".local" / "share" / "home_guard"
ZONE_LIST_FILE: Final = DATA_DIR / ".zone_list"
ZONE_CURSOR_FILE: Final = DATA_DIR / ".zone_cursor"
CHALLENGE_STORE_FILE: Final = DATA_DIR / "challenges.json"
CLEAR_LOG_FILE: Final = DATA_DIR / "clear_log.json"
PHOTOS_DIR: Final = DATA_DIR / "photos"
ESCAPE_HATCH_HISTORY_FILE: Final = DATA_DIR / ".escape_hatch_history"

# Shared with every sibling locker on purpose -- one key, one place, same as
# leetcode-guard's own install.sh does (its ensure_hmac_key() checks this
# exact path). The isolation a home-guard-only key would buy is illusory:
# every sibling app runs as the same user, so a compromise that could forge
# home-guard's entries could equally read this file directly regardless of
# which filename it lives under. Never change this path -- doing so would
# invalidate every already-signed entry across all five lockers.
HMAC_KEY_FILE: Final = Path("/etc/workout-locker/hmac.key")

# Fixed-slot cadence, mirroring diet-guard's shape. One slot per day by
# default -- clearing a zone is not a multiple-times-daily activity the way
# eating is.
GATE_DAY_START_HOUR: Final = 8
GATE_SLOT_INTERVAL_HOURS: Final = 24
GATE_WINDOW_END_HOUR: Final = 22

DEFAULT_ZONES: Final = ("desk", "kitchen counter", "entryway")

# Firebase RTDB path prefix (shared kuhy-syncs project, per-app prefix, same
# pattern as todo/home_inventory/wake-alarm).
SYNC_PREFIX: Final = "home-guard-sync"
SYNC_CHALLENGE_PATH: Final = f"{SYNC_PREFIX}/challenge/current.json"
SYNC_EVIDENCE_PATH: Final = f"{SYNC_PREFIX}/evidence/current.json"

# Decoded-photo size cap. The phone app re-encodes at a lower JPEG quality
# to stay under this before ever uploading; _sync_evidence.save_evidence_photo
# enforces the same number server-side, so a stale app build or a stray
# upload can never write an unbounded blob to disk regardless of what the
# client claims to have capped.
MAX_EVIDENCE_PHOTO_BYTES: Final = 600_000

POLL_INTERVAL_MS: Final = 5_000
POLL_DRAIN_MS: Final = 200
