# AGENTS.md — home-guard

Photo-verified, zone-rotating home-tidy gate. Fifth sibling to
`screen-locker`/`diet-guard`/`leetcode-guard`/`wake-alarm`, built on the
shared `gatelock` (lock-window + arbiter) and `crdt_sync` (Firebase RTDB
sync) libraries. `CLAUDE.md` is a symlink to this file.

Full design rationale lives in `README.md` and
`docs/DOCS-marker-protocol.md`/`docs/DOCS-zone-rotation.md`. This file is
commands + conventions only.

## Commands

- Tests + coverage: `python3 -m pytest home_guard/tests/ -q --cov=home_guard --cov-report=term-missing`
  (currently ~120 tests, 100% coverage on every module except `_lock.py`/
  `_view.py` — see their docstrings for why, and `tests/test_lock_integration.py`
  for how those two are actually verified).
- Lint: `ruff check .` / format: `ruff format .`. **Never run
  `ruff check --fix --unsafe-fixes` blind** — it has silently deleted
  `print()` calls in this exact repo (ruff's T201 "unsafe fix" strips the
  call entirely). Only ever use plain `--fix` (safe fixes) or `ruff format`,
  and re-run the test suite immediately after either.
- Run the CLI directly: `python -m home_guard {init,status,gate,gate --demo}`.
- MCP server venv: `./scripts/setup_mcp.sh` (see README's MCP section).
- Git hooks on a fresh clone: `scripts/install_hooks.sh` (pre-commit + pre-push
  + the post-gate version bump for `app/pubspec.yaml`; see the script for
  why the bump is not a pre-commit hook).
- Install for real (not run automatically by any agent session — this
  enables a systemd timer that can lock the screen): `bash install.sh`.

## Architecture

`home_guard/` — Python package, one file one responsibility, ~250 line cap:

- `_constants.py` — every path, the arbitration rank, cadence constants.
- `_zone_list.py` / `_zone_cursor.py` — the rotation: a forward-only edit
  history (like diet-guard's meal-schedule history) plus a plain
  current-pointer that advances only on an accepted photo clear.
- `_slots.py` / `_gate.py` — pure due-slot arithmetic, mirrors
  `diet_guard/_gate.py`'s `due_slots`/`gate_is_due` shape exactly.
- `_challenge.py` / `_challenge_store.py` — the publish-then-echo anti-replay
  mechanism (mint a single-use token, verify the phone's echo).
- `_log.py` / `_log_store.py` — the HMAC-signed clear/escape log. Two entry
  kinds only (`clear` from a verified photo, `escape` from the bounded
  hatch) — there is deliberately no automatic, no-justification third kind;
  an earlier draft's silent network-outage exemption was an unbounded
  exploit and was removed (see `_log.py`'s module docstring).
- `_escape_hatch.py` — wraps `gatelock.EscapePolicy`/`EscapeTracker` with
  home-guard's own policy/history file. Grants a slot but never rotates the
  zone — the zone was never actually verified clear.
- `_sync_client.py` / `_sync_challenge.py` / `_sync_evidence.py` — Firebase
  RTDB wiring. `ConfigError` is caught explicitly everywhere alongside
  `RemoteSyncError` (it does not subclass it — the exact gotcha diet-guard's
  own `_sync_client.py` flags).
- `_netcheck.py` / `_network_incident.py` — classify a publish failure
  (remote outage vs this machine's own network) for UI messaging only;
  arming never depends on either.
- `_accept.py` — the full verify → photo → log → rotate → drain pipeline.
- `_poller.py` — polls Firebase off the Tk thread via a `ThreadPoolExecutor`,
  never lets a check exception kill the loop.
- `_lock.py` / `_view.py` — the gatelock wiring (Arbiter/LockConfig/
  LockWindow) and the Tk widgets. See their docstrings re: coverage.
- `_paths.py` — `HomeGuardPaths`, the one bundle every path-taking function
  accepts instead of individual `*_path`/`*_key_file` kwargs (keeps
  `ruff`'s PLR0913 clean and gives tests one override point that can never
  leak into real `~/.local/share/home_guard` state).
- `_cli*.py` / `__main__.py` — `init`/`status`/`gate` subcommands.
- `_mcp.py` — read-only MCP server, no write tool at all (see README).

## Testing conventions

- Every path/key-file parameter defaults to the real on-disk location but
  is always overridable; **tests must always pass explicit tmp_path-rooted
  overrides** — never rely on a module-level default in a test, even
  indirectly through a function that resolves one internally. A past bug in
  this exact repo had a test read/write the real `~/.local/share/home_guard`
  because it patched the wrong module's copy of an imported name (see git
  history around `_network_incident.py`'s first draft).
- When patching a name for a test, patch it in the **consuming** module's
  namespace (`from X import Y` binds a new reference in the importing
  module), not the **defining** module's — patching the source module does
  nothing to an already-bound import elsewhere.
- The Tk lock window is tested via a real Xvfb display
  (`tests/conftest.py`'s `xvfb_display` fixture) in a **subprocess** with
  `HOME` redirected before its first import — several modules (including
  `crdt_sync`'s own config path) resolve `Path.home()` into module-level
  constants at import time, so patching the environment in-process after
  those modules are already imported does not isolate anything.
- `GATELOCK_RUNTIME_DIR` must be redirected in any test that arms a real
  `gatelock.Arbiter` — otherwise it reads the real shared arbiter claims
  directory and can hang for up to 6 hours waiting behind an actually-running
  sibling gate on the developer's real machine.

## Git workflow

- Commit and push to `main` directly, same as the sibling repos. No feature
  branches for normal work.
- End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
