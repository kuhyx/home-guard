#!/bin/bash
# ============================================================================
# deploy.sh -- deploy home-guard everywhere it runs: the desktop gate (an
# editable install of ~/src/home-guard under the system python) and the
# Flutter app on the Pixel (release build via phone_deploy.sh).
#
# CLAUDE.md's deploy line pulls ~/src/home-guard first and then runs THIS
# copy from there, so the freshly pulled script is what executes.
#
# Idempotent: a second run changes nothing (pip is skipped when the live
# import already resolves to ~/src/home-guard; the phone is skipped when the
# installed versionName already matches app/pubspec.yaml).
#
# Leaves the armed state exactly as found. While the DISARMED marker exists
# it never runs install.sh (which would re-enable the lock timer) and fails
# if either unit's enablement changed during the run.
#
# Usage: scripts/deploy.sh [--desktop-only | --build-only]
#   --desktop-only  skip the phone step entirely
#   --build-only    build the release APK but do not install it (board
#                   sessions, which phone_deploy refuses to install from)
# Exit: 0 every health check passed, 1 a step failed (named on stderr).
# ============================================================================

set -euo pipefail

readonly LIVE_REPO="${HOME_GUARD_LIVE_REPO:-$HOME/src/home-guard}"
readonly SYSTEM_PYTHON="/usr/bin/python3"
readonly PHONE_DEPLOY="${PHONE_DEPLOY:-$HOME/.claude/scripts/phone_deploy.sh}"
readonly SERIAL="${ADB_SERIAL:-23181JEGR08034}"
readonly PACKAGE="com.kuhy.home_guard"
readonly UNITS=("home-guard-gate.timer" "home-guard-gate.service")
# Same default as scripts/disarm_guard.sh and _constants.DISARM_MARKER_FILE.
readonly DISARM_MARKER="${DISARM_MARKER:-$HOME/.local/share/home_guard/DISARMED}"

log() { printf 'deploy: %s\n' "$1" >&2; }
fail() { printf 'deploy: FAILED [%s] -- %s\n' "$1" "$2" >&2; exit 1; }

# Run the system python from / so a checkout in the cwd can never shadow the
# live editable install (it did, from a worktree, while this was written).
live_python() { (cd / && "$SYSTEM_PYTHON" "$@"); }

update_checkout() {
    log "pulling $LIVE_REPO"
    git -C "$LIVE_REPO" pull --ff-only --quiet || fail pull "git pull --ff-only in $LIVE_REPO"
}

install_package() {
    local file
    file=$(live_python -c 'import home_guard; print(home_guard.__file__)' 2>/dev/null || true)
    if [[ $file == "$LIVE_REPO/home_guard/"* ]]; then
        log "editable install already points at $LIVE_REPO"
        return
    fi
    log "installing $LIVE_REPO into the system python (editable)"
    live_python -m pip install --quiet --user --break-system-packages -e "$LIVE_REPO" \
        || fail pip "pip install -e $LIVE_REPO"
}

check_desktop() {
    local file out
    live_python -c 'import home_guard, gatelock, crdt_sync, freedays' \
        || fail imports "a runtime dependency is missing from $SYSTEM_PYTHON"
    file=$(live_python -c 'import home_guard; print(home_guard.__file__)')
    [[ $file == "$LIVE_REPO/home_guard/"* ]] || fail imports "home_guard resolves to $file"
    out=$(live_python -m home_guard status) || fail status "home_guard status exited non-zero"
    [[ $out == *"due slots today:"* ]] || fail status "no due-slots line in: $out"
    log "desktop OK: $(grep -m1 'due slots today:' <<<"$out")"
}

unit_states() {
    local unit
    for unit in "${UNITS[@]}"; do
        printf '%s=%s ' "$unit" "$(systemctl --user is-enabled "$unit" 2>/dev/null || true)"
    done
}

deploy_units() {
    if [[ -f $DISARM_MARKER ]]; then
        log "DISARMED marker present: units left as they are"
        return
    fi
    log "armed: re-running install.sh"
    bash "$LIVE_REPO/install.sh" || fail install "install.sh"
    systemctl --user is-active --quiet home-guard-gate.timer \
        || fail timer "home-guard-gate.timer is not active"
}

pubspec_version_name() {
    local line
    line=$(grep -m1 '^version:' "$LIVE_REPO/app/pubspec.yaml") || fail phone "no version in pubspec.yaml"
    line=${line#version:}
    line=${line// /}
    printf '%s\n' "${line%%+*}"
}

# Empty when the phone is unreachable or the app absent; phone_deploy then
# names the real failure. No pipe, so pipefail cannot exit here silently.
installed_version_name() {
    local dump
    dump=$(adb -s "$SERIAL" shell dumpsys package "$PACKAGE" 2>/dev/null | tr -d '\r' || true)
    sed -n '/^ *versionName=/{s///;p;q}' <<<"$dump"
}

build_apk() {
    local stage
    for stage in prep dart kotlin assemble; do
        log "phone: release build stage $stage"
        "$PHONE_DEPLOY" "$LIVE_REPO/app" --release --stage "$stage" \
            || fail "phone-$stage" "phone_deploy.sh --stage $stage"
    done
}

deploy_phone() {
    local want have
    want=$(pubspec_version_name)
    have=$(installed_version_name)
    if [[ $have == "$want" ]]; then
        log "phone already runs $PACKAGE $want"
        return
    fi
    log "phone: $PACKAGE ${have:-absent} -> $want"
    # phone_deploy never uninstalls or clears data; its own exit code names
    # the failure (30 unreachable, 32 signature change, 35 install, ...).
    "$PHONE_DEPLOY" "$LIVE_REPO/app" --release || fail phone "phone_deploy.sh exited $?"
    have=$(installed_version_name)
    [[ $have == "$want" ]] || fail phone "installed versionName '$have', want '$want'"
    log "phone OK: $PACKAGE $have"
}

main() {
    local mode="${1:-all}" before after
    case "$mode" in
        all | --desktop-only | --build-only) ;;
        *) fail usage "unknown option $mode (use --desktop-only or --build-only)" ;;
    esac
    before=$(unit_states)
    update_checkout
    install_package
    check_desktop
    deploy_units
    if [[ -f $DISARM_MARKER ]]; then
        after=$(unit_states)
        [[ $after == "$before" ]] || fail disarmed "unit state changed: $before -> $after"
    fi
    case "$mode" in
        --desktop-only) ;;
        --build-only) build_apk ;;
        *) deploy_phone ;;
    esac
    log "done"
}

main "$@"
