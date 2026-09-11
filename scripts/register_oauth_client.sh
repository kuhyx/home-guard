#!/bin/bash

# ============================================================================
# Walks the one step that cannot be automated -- registering this app's Android
# OAuth client -- and runs everything around it that can be.
#
# Why a human has to click: an OAuth client is a credential, and Google exposes
# no create API for one. `gcloud` has no command, the Firebase CLI has no
# command, and the console is the only path. Everything either side of that
# click is done here.
#
# Until it is done, Google sign-in fails with UNREGISTERED_ON_API_CONSOLE, which
# Android's Credential Manager surfaces as the far less helpful
# "canceled: account reauth failed" -- so the symptom names the account when
# the cause is the console.
#
# What this does for you:
#   * derives the SHA-1 from the real keystore, so the value pasted into the
#     console cannot be a stale copy of one;
#   * opens the console and puts each field on the clipboard in form order;
#   * verifies on the phone afterwards by reading the home screen back: it
#     asks the keystore for a session, so a revoked one shows as disconnected.
#
# Usage:
#   scripts/register_oauth_client.sh              # register, then verify
#   scripts/register_oauth_client.sh --verify-only
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
readonly CONSOLE_URL="https://console.cloud.google.com/auth/clients?project=kuhy-syncs"
readonly PACKAGE="com.kuhy.home_guard"
readonly DEVICE="23181JEGR08034"
readonly DUMP=/tmp/home_guard_ui.xml

log() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
step() { printf '   %s\n' "$1"; }

# Copies to the clipboard when a tool is available; prints regardless, so this
# still works over ssh with no X display.
clip() {
    if command -v xclip >/dev/null 2>&1; then
        printf '%s' "$1" | xclip -selection clipboard 2>/dev/null || true
        printf '   \033[32m[copied]\033[0m %s\n' "$1"
    else
        printf '   %s\n' "$1"
    fi
}

pause() { read -rp "   ...press Enter when that field is filled " _; }

# Reads the release signing fingerprint out of the keystore itself.
#
# Derived rather than hardcoded: a fingerprint copied into a doc goes stale
# silently, and the failure it causes looks nothing like "wrong SHA-1".
release_sha1() {
    local properties="$REPO_DIR/app/android/key.properties"
    if [[ ! -f "$properties" ]]; then
        echo "error: $properties not found; cannot derive the SHA-1" >&2
        return 1
    fi
    local store password alias
    store="$(grep -E '^storeFile=' "$properties" | cut -d= -f2-)"
    password="$(grep -E '^storePassword=' "$properties" | cut -d= -f2-)"
    alias="$(grep -E '^keyAlias=' "$properties" | cut -d= -f2-)"
    [[ "$store" = /* ]] || store="$REPO_DIR/app/android/$store"
    keytool -list -v -keystore "$store" -alias "$alias" \
        -storepass "$password" 2>/dev/null |
        grep -E '^[[:space:]]*SHA1:' | head -1 | sed 's/.*SHA1: //' | tr -d ' \r'
}

# Dumps the current screen so nodes can be found by their text.
dump_ui() {
    adb -s "$DEVICE" shell uiautomator dump /sdcard/hg_ui.xml >/dev/null 2>&1
    adb -s "$DEVICE" pull /sdcard/hg_ui.xml "$DUMP" >/dev/null 2>&1
}

# Launches the app and reads its home screen. The headline is "Not
# connected" until the keystore holds a Firebase session, and the zone (or
# "Nothing due") once it does -- so this asks the keystore, not a local flag.
verify_on_phone() {
    log "Verifying on the phone"
    if ! adb devices | grep -q "^$DEVICE"; then
        step "phone not attached; reconnect it and rerun with --verify-only"
        return 1
    fi
    adb -s "$DEVICE" shell am start -n "$PACKAGE/.MainActivity" >/dev/null 2>&1
    sleep 5
    local top
    top="$(adb -s "$DEVICE" shell dumpsys activity activities 2>/dev/null |
        grep -m1 topResumedActivity | grep -o 'com\.[a-z_.]*' | head -1)"
    if [[ "$top" != "$PACKAGE" ]]; then
        step "foreground app is '$top', not $PACKAGE -- cannot read the screen"
        return 1
    fi
    dump_ui
    if PYTHONPATH="$REPO_DIR" python3 -m home_guard._ui_dump "$DUMP" has "Not connected"; then
        log "NOT CONNECTED yet."
        step "Tap the gear -> Sync settings -> 'Sign in with Google' and pick"
        step "321krzychu@gmail.com -- the uid the database rules pin. Any other"
        step "account signs in fine and is then denied every read and write."
        step "Then rerun: scripts/register_oauth_client.sh --verify-only"
        return 1
    fi
    log "CONNECTED — this device holds a session."
    step "The home screen now shows the zone the PC is waiting on (or"
    step "'Nothing due' when no slot is due)."
}

main() {
    if [[ "${1:-}" == "--verify-only" ]]; then
        verify_on_phone
        return
    fi

    local sha1
    sha1="$(release_sha1)"
    if [[ -z "$sha1" ]]; then
        echo "error: could not read a SHA-1 from the keystore" >&2
        exit 1
    fi

    log "Register ONE Android OAuth client in project kuhy-syncs"
    step "Google has no API for this. One form, three fields."
    printf '\n'

    if command -v xdg-open >/dev/null 2>&1; then
        step "Opening the console..."
        xdg-open "$CONSOLE_URL" >/dev/null 2>&1 &
    else
        step "$CONSOLE_URL"
    fi
    sleep 2

    step "Click '+ CREATE CLIENT', set Application type = Android."
    printf '\n'
    step "Field 'Name':"
    clip "home-guard"
    pause
    step "Field 'Package name':"
    clip "$PACKAGE"
    pause
    step "Field 'SHA-1 certificate fingerprint':"
    clip "$sha1"
    pause
    step "Click CREATE."
    pause

    log "Done in the console. Do NOT touch the existing Web client."
    step "It is already the audience this app's tokens are minted for."

    printf '\n'
    read -rp "   Registration takes a minute to propagate. Enter to verify: " _
    verify_on_phone
}

main "$@"
