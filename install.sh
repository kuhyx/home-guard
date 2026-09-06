#!/bin/bash
# ============================================================================
# install.sh -- install home-guard for real use.
#
# Installs into the SYSTEM python's user site-packages, not a venv, because
# that is what the systemd unit actually runs (mirrors diet-guard's and
# leetcode-guard's own install.sh, including the exact "verify with the
# interpreter systemd will use" step that caught diet_guard being silently
# dead for three days on the wrong interpreter).
#
# Idempotent. Safe to re-run after any change.
#
# This script does NOT enable anything with sudo. The HMAC key step only
# prints the command to run yourself if you want signed log entries; the
# gate itself works (just with unsigned entries) even if you never run it.
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_DIR
readonly SYSTEM_PYTHON="/usr/bin/python3"
readonly UNIT_DIR="${HOME}/.config/systemd/user"
readonly HMAC_KEY="/etc/workout-locker/hmac.key"

log() { printf 'install: %s\n' "$1" >&2; }
fail() { printf 'install: FAILED -- %s\n' "$1" >&2; exit 1; }

install_package() {
    log "installing into the system python's user site-packages"
    "$SYSTEM_PYTHON" -m pip install --user --break-system-packages -e "$REPO_DIR" \
        || fail "pip install"
}

verify_imports() {
    # The check that matters: every runtime dependency must resolve for the
    # interpreter systemd will launch, not for whatever is on $PATH now.
    log "verifying imports with $SYSTEM_PYTHON"
    "$SYSTEM_PYTHON" -c "import home_guard, gatelock, crdt_sync; print('imports OK')" \
        || fail "a runtime dependency is missing from the system python"
}

ensure_hmac_key() {
    # Shared with the sibling lockers on purpose -- one key, one place. See
    # _constants.py's HMAC_KEY_FILE docstring for why this is not a
    # home-guard-only key.
    if [[ -r "$HMAC_KEY" ]]; then
        log "HMAC key present and readable at $HMAC_KEY"
        return
    fi
    if [[ -e "$HMAC_KEY" ]]; then
        fail "$HMAC_KEY exists but is not readable -- log integrity would be off"
    fi
    log "no HMAC key at $HMAC_KEY"
    log "  clear/escape log entries will be unsigned until one exists."
    log "  create it with: sudo install -d -m 755 /etc/workout-locker &&"
    log "    sudo $SYSTEM_PYTHON -c \\"
    log "      'from gatelock.log_integrity import generate_hmac_key; generate_hmac_key()'"
}

seed_zone_rotation() {
    # Must happen before the timer can ever fire -- an unseeded zone list
    # still resolves (DEFAULT_ZONES), but seeding now makes `home_guard
    # status` and the MCP server's get_zone_rotation() show real history
    # from day one rather than a synthetic fallback.
    log "seeding the zone rotation (safe to re-run; leaves an edited list alone)"
    "$SYSTEM_PYTHON" -m home_guard init
}

install_units() {
    log "installing systemd user units into $UNIT_DIR"
    mkdir -p "$UNIT_DIR"
    install -m 644 "$REPO_DIR/home-guard-gate.service" "$UNIT_DIR/"
    install -m 644 "$REPO_DIR/home-guard-gate.timer" "$UNIT_DIR/"
    systemctl --user daemon-reload
    systemctl --user enable --now home-guard-gate.timer
    log "timer enabled; next run:"
    systemctl --user list-timers home-guard-gate.timer --no-pager || true
}

main() {
    install_package
    verify_imports
    ensure_hmac_key
    seed_zone_rotation
    install_units
    log "done. Test the lock now (safe, closeable): python3 -m home_guard gate --demo"
}

main "$@"
