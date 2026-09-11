# home-guard

Locks the PC until you clear the currently-assigned zone of your home,
verified with a photo — not a claim. Fifth sibling to
[`screen-locker`](https://github.com/kuhyx/screen-locker) (workouts),
[`diet-guard`](https://github.com/kuhyx/diet-guard) (meals),
[`leetcode-guard`](https://github.com/kuhyx/leetcode-guard) (practice) and
[`wake-alarm`](https://github.com/kuhyx/wake-alarm) (mornings), built on the
same shared [`gatelock`](https://github.com/kuhyx/utils/tree/main/gatelock)
lock-window + arbiter backend.

## How it decides

A rotating, single-zone assignment on a fixed daily slot, mirroring
diet-guard's "slot elapses without a log → lock" shape: one zone (desk,
kitchen counter, entryway, ...) is due at a time; clear it and the rotation
moves to the next. No zone is ever "done forever" — the same list keeps
cycling.

**Evidence is a photo, but the photo is never graded.** No model — vision or
otherwise — ever judges whether a room is actually tidy; that would put an
LLM in a pass/fail adjudication loop, which this family's tooling avoids on
principle. Instead:

1. When a slot is due, the PC mints a single-use token and publishes it to
   Firebase RTDB (transport only, never storage).
2. The phone app fetches the token, shows the assigned zone, and — after an
   **in-app camera-only** photo (no gallery picker, so an old photo can't be
   substituted) — uploads the photo with the token echoed back verbatim.
3. The PC accepts only if the echoed token matches what it itself issued and
   hasn't already been consumed. The photo is decoded, written to disk for
   accountability, and the RTDB node is drained immediately.

No shared secret ever reaches the phone (see
[`docs/DOCS-marker-protocol.md`](docs/DOCS-marker-protocol.md) for why a
publish-then-echo design beats provisioning one).

**A genuine sync outage never grants a silent, unlimited pass.** The lock
still arms on schedule regardless of network state — an offline machine
locks exactly like every sibling gate. The only way past a slot the
automatic path can't verify is a bounded, justified escape hatch (rolling
budget, escalating lockout, written reason — the same "sick mode" mechanism
`gatelock.EscapePolicy`/`EscapeTracker` gives screen-locker), which excuses
*that slot* without ever rotating the zone or claiming it was actually
cleared.

## Install

```bash
bash install.sh
```

Installs the package into the system Python's user site-packages (the
systemd service runs `/usr/bin/python` directly, not a venv), installs the
gate's systemd user timer, and seeds the zone rotation. Does **not** run
anything with `sudo` — the HMAC key step only prints the command to run
yourself if you want signed log entries; the gate works (with unsigned
entries) even if you never run it.

It **refuses to enable the timer without a desktop Firebase session**
(`~/.config/home_guard/firebase_auth.json`): a gate that can't publish its
challenge can never be satisfied by a photo, so every slot would burn
escape-hatch budget. Seed one first — an interactive Google consent
round-trip that deliberately seeds every desktop app together:

```bash
python3 ~/src/utils/crdt-sync/tool/seed_session.py
```

## Usage

```bash
python -m home_guard init            # seed/inspect the zone rotation (idempotent)
python -m home_guard status          # read-only: is the gate due, for which zone
python -m home_guard gate            # what systemd actually runs every ~30 min
python -m home_guard gate --demo     # soft, closeable lock — safe to try
```

## Phone app

`app/` is the Flutter half (`com.kuhy.home_guard`, Android). One screen: the
zone the PC is waiting on and a single **Take photo** button that opens the
in-app camera — there is no gallery picker anywhere, on purpose. After the
upload it watches the evidence node until the PC drains it and reports
"accepted". Firebase-only, signed in through the shared Sync settings screen
(Google one-tap, account `321krzychu@gmail.com`).

```bash
~/.claude/scripts/phone_deploy.sh ~/src/home-guard/app --release   # build + install
scripts/register_oauth_client.sh   # one-time: Android OAuth client (console)
scripts/set_release_secrets.sh     # one-time: CI signing secrets
```

Tests: `cd app && flutter analyze && flutter test --coverage` (100% line
coverage; the camera and keystore adapters are `coverage:ignore` platform
channels and are exercised on the phone instead). CI (`release-apk.yml`) runs
analyze + test and only then publishes a signed APK per commit.

## Testing

```bash
python3 -m pytest home_guard/tests/ -q --cov=home_guard --cov-report=term-missing
```

100% coverage on every module except the Tk lock window (`_lock.py`,
`_view.py`), which is verified instead by `tests/test_lock_integration.py` —
a real, automated end-to-end run against an isolated Xvfb display and a
fresh `GATELOCK_RUNTIME_DIR`, so it never touches the developer's real
screen or the real shared arbiter state used by their actually-running
sibling gates. See `_lock.py`'s module docstring for why the coverage
percentage under-reports that file (the test runs in a subprocess).

## MCP server (Claude Code integration)

Read-only, like screen-locker's. Four tools: `get_status`,
`get_zone_rotation`, `get_clear_history`, `explain_lock`. **No write tool at
all** — unlike diet-guard's one gated `log_meal`, home-guard's entire point
is that a claim alone, even one entered by an MCP client on the user's
behalf, must never count.

```bash
./scripts/setup_mcp.sh
```

Restart Claude Code in this repo and approve the project MCP-server prompt.
