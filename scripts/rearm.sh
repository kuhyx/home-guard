#!/bin/bash

# ============================================================================
# rearm.sh -- deliberately undo ./scripts/disarm.sh.
#
# Clears the marker, restores the stashed unit files, unmasks, and re-enables
# the timer. Kept separate from install.sh on purpose: re-arming a gate that
# can lock the screen should be a thing you typed, not a side effect of
# reinstalling.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

# shellcheck source=disarm_guard.sh
source "$SCRIPT_DIR/disarm_guard.sh"

main() {
	if [[ ! -f $DISARM_MARKER ]]; then
		echo "Not disarmed (no marker at $DISARM_MARKER)."
	fi

	clear_disarm_marker

	if [[ ! -f "$DISARM_UNIT_DIR/home-guard-gate.timer" ]]; then
		echo "No unit file at $DISARM_UNIT_DIR/home-guard-gate.timer." >&2
		echo "Run ./install.sh to reinstall the units, then re-run this." >&2
		exit 1
	fi

	systemctl --user enable --now home-guard-gate.timer
	echo "Timer re-enabled; next run:"
	systemctl --user list-timers home-guard-gate.timer --no-pager || true
}

main "$@"
