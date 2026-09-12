#!/bin/bash

# ============================================================================
# disarm.sh -- stop home-guard from ever locking the screen, durably.
#
# Three steps, because any one alone is defeatable:
#   1. disable + stop the timer      (systemd stops scheduling it)
#   2. stash the unit files, mask    (a hand-run `systemctl start` fails too)
#   3. write the marker              (install.sh and `python -m home_guard
#                                     gate` both refuse while it exists)
#
# Idempotent. Reverse it with ./scripts/rearm.sh.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

# shellcheck source=disarm_guard.sh
source "$SCRIPT_DIR/disarm_guard.sh"

REASON=""

usage() {
	echo "Usage: $(basename "$0") [--reason TEXT]"
	echo "Options:"
	echo "  -r, --reason TEXT   Why it is disarmed; shown by every banner"
	echo "  -h, --help          Show this help"
	exit 0
}

stop_timer() {
	# --now stops the timer as well as disabling it. Never touches a running
	# gate service: if a lock is up right now, the user is looking at it and
	# killing it from under them is not this script's business.
	if systemctl --user is-enabled home-guard-gate.timer >/dev/null 2>&1; then
		systemctl --user disable --now home-guard-gate.timer
	else
		echo "Timer already disabled."
	fi
}

stash_and_mask() {
	local stash unit masked_any=0

	# `systemctl mask` wants to put a /dev/null symlink where the unit file is
	# and refuses if a regular file is already there -- which is exactly what
	# install.sh leaves behind. Move them aside first, into a timestamped dir
	# rearm.sh restores from.
	stash="$DISARM_UNIT_DIR/disabled-$(date +%Y%m%d-%H%M%S)"
	for unit in "${MASKED_UNITS[@]}"; do
		if [[ -f "$DISARM_UNIT_DIR/$unit" && ! -L "$DISARM_UNIT_DIR/$unit" ]]; then
			mkdir -p "$stash"
			mv "$DISARM_UNIT_DIR/$unit" "$stash/$unit"
			masked_any=1
		fi
	done
	[[ $masked_any -eq 1 ]] && echo "Stashed unit files in $stash"

	for unit in "${MASKED_UNITS[@]}"; do
		if [[ $(systemctl --user is-enabled "$unit" 2>/dev/null) == masked* ]]; then
			continue
		fi
		systemctl --user mask "$unit"
	done
	systemctl --user daemon-reload
}

write_marker() {
	local text
	text="${REASON:-disarmed on $(date -Iseconds)}"
	mkdir -p "$(dirname "$DISARM_MARKER")"
	printf '%s\n' "$text" >"$DISARM_MARKER"
	echo "Wrote marker: $DISARM_MARKER"
}

main() {
	stop_timer
	stash_and_mask
	write_marker
	echo ""
	report_disarmed
	echo ""
	echo "Verify:  systemctl --user list-timers --all | grep home-guard  (expect nothing)"
	echo "Re-arm:  ./scripts/rearm.sh"
}

while [[ $# -gt 0 ]]; do
	case $1 in
	-r | --reason)
		REASON="$2"
		shift 2
		;;
	-h | --help)
		usage
		;;
	*)
		echo "Unknown option: $1" >&2
		exit 1
		;;
	esac
done

main
