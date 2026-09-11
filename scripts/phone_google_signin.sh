#!/bin/bash

# ============================================================================
# phone_google_signin.sh -- sign the phone app into the sync account over adb.
#
# Deploys the `lib/main_google_signin.dart` autodrive entrypoint (which opens
# the Google one-tap picker on launch), taps the sync account in the NATIVE
# account sheet -- found by text via uiautomator, never a blind coordinate --
# reads the verdict the probe prints to logcat, then redeploys the normal
# entrypoint. The keystore session survives the redeploy (same package, same
# signing key, `adb install -r`).
#
# Precondition: an Android OAuth client for com.kuhy.home_guard + the release
# SHA-1 must exist in project kuhy-syncs (scripts/register_oauth_client.sh).
# Without it the picker appears, the account is chosen, and gms hands back
# nothing -- this script reports that as CANCELLED, which is the console's
# fault, not the phone's.
#
# Usage: scripts/phone_google_signin.sh [--account <email>] [--keep-probe]
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
readonly DEPLOY="${HOME}/.claude/scripts/phone_deploy.sh"
readonly DUMP=/tmp/home_guard_ui.xml
ACCOUNT="321krzychu@gmail.com"
KEEP_PROBE=0

log() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
step() { printf '   %s\n' "$1"; }

ui_centre() {
    adb shell uiautomator dump /sdcard/hg_ui.xml >/dev/null 2>&1
    adb pull /sdcard/hg_ui.xml "$DUMP" >/dev/null 2>&1
    PYTHONPATH="$REPO_DIR" python3 -m home_guard._ui_dump "$DUMP" centre "$1"
}

# The probe's verdict line, or empty. Read from logcat because uiautomator
# cannot see Flutter text.
verdict() {
    adb logcat -d -t 3000 2>/dev/null | grep -oE 'probe: [A-Z ]+[^"]*' | tail -1 || true
}

deploy() {
    bash "$DEPLOY" "$REPO_DIR/app" --release "$@" 2>&1 |
        grep -E 'Built|Success|rror' || true
}

main() {
    adb logcat -c
    log "Deploying the sign-in probe entrypoint"
    deploy --target lib/main_google_signin.dart

    log "Waiting for the account picker"
    local coords=""
    for _ in $(seq 1 15); do
        sleep 2
        coords="$(ui_centre "$ACCOUNT" 2>/dev/null || true)"
        [[ -n "$coords" ]] && break
        if verdict | grep -q 'ALREADY SIGNED IN'; then
            step "already signed in; nothing to do"
            coords=""
            break
        fi
    done
    if [[ -n "$coords" ]]; then
        local x y
        read -r x y <<<"$coords"
        adb shell input tap "$x" "$y"
        step "tapped $ACCOUNT at ($x, $y)"
    fi

    log "Reading the verdict"
    local result=""
    for _ in $(seq 1 15); do
        sleep 2
        result="$(verdict)"
        [[ -n "$result" && "$result" != *starting* ]] && break
    done
    step "${result:-no verdict from the probe (see adb logcat)}"

    if [[ "$KEEP_PROBE" == 0 ]]; then
        log "Restoring the normal entrypoint"
        deploy
    fi

    [[ "$result" == *"SIGNED IN"* ]]
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --account) ACCOUNT="$2"; shift 2 ;;
        --keep-probe) KEEP_PROBE=1; shift ;;
        -h|--help) sed -n '3,20p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

main "$@"
