#!/bin/bash

# ============================================================================
# Disarm guard — shared by install.sh, disarm.sh and rearm.sh.
#
# Ported from ~/src/screen-locker/scripts/disarm_guard.sh, and for the same
# reason: masking the systemd units is not enough on its own. install.sh
# *copies* unit files into ~/.config/systemd/user, which silently overwrites
# systemd's /dev/null mask symlinks and re-enables the timer. So a mask alone
# loses to anyone — including a future agent session — running the obvious
# install command by reflex.
#
# The marker file is the deliberate second step: while it exists, no script
# may install units or enable the timer. Removing it is an explicit rearm.sh.
#
# Source this file; it defines DISARM_MARKER, UNIT_DIR, MASKED_UNITS,
# report_disarmed, refuse_if_disarmed and clear_disarm_marker.
# ============================================================================

# Machine-scoped, deliberately OUTSIDE the repo: a marker inside the checkout
# would be erased by `git clean` and is gitignored state anyway. This guards
# the machine, not the checkout. Shares DATA_DIR with home_guard/_constants.py
# (DISARM_MARKER_FILE) so the Python gate reads the exact same file.
DISARM_MARKER="${DISARM_MARKER:-$HOME/.local/share/home_guard/DISARMED}"
readonly DISARM_MARKER

DISARM_UNIT_DIR="${DISARM_UNIT_DIR:-$HOME/.config/systemd/user}"
readonly DISARM_UNIT_DIR

# The timer is what schedules the gate; the service is what runs it. Both are
# masked so neither `start` nor a stray `Wants=` can reach the lock.
MASKED_UNITS=("home-guard-gate.timer" "home-guard-gate.service")
readonly MASKED_UNITS

# Print the disarmed banner. Returns 0 when disarmed, 1 when armed.
report_disarmed() {
	[[ -f $DISARM_MARKER ]] || return 1
	echo "================================================================"
	echo "  HOME-GUARD DISARMED - the tidy gate will not lock the screen."
	echo "================================================================"
	echo "Marker: $DISARM_MARKER"
	if [[ -s $DISARM_MARKER ]]; then
		sed 's/^/  | /' "$DISARM_MARKER"
	fi
	return 0
}

# Hard stop for any path that installs units or enables the timer.
# Read-only paths should call report_disarmed instead.
refuse_if_disarmed() {
	report_disarmed || return 0
	echo "" >&2
	echo "Refusing to arm while disarmed. To re-arm deliberately:" >&2
	echo "    ./scripts/rearm.sh" >&2
	exit 1
}

# Remove the marker, restore any stashed unit files and unmask, so a
# subsequent install can proceed.
clear_disarm_marker() {
	local unit stash newest

	if [[ -f $DISARM_MARKER ]]; then
		rm -f "$DISARM_MARKER"
		echo "Removed disarm marker: $DISARM_MARKER"
	fi

	for unit in "${MASKED_UNITS[@]}"; do
		# is-enabled prints "masked" for masked units; unmask only those, so a
		# normal re-arm does not spew errors about units that were never masked.
		if [[ $(systemctl --user is-enabled "$unit" 2>/dev/null) == masked* ]]; then
			systemctl --user unmask "$unit"
		fi
	done

	# Restore the real unit files that disarm.sh moved aside. Masking replaces
	# them with /dev/null symlinks, so without this the units exist only as
	# whatever install.sh happens to copy back -- and rearm.sh must work on its
	# own, not only as a prelude to a reinstall.
	newest=""
	for stash in "$DISARM_UNIT_DIR"/disabled-*/; do
		[[ -d $stash ]] || continue
		newest="$stash"
	done
	if [[ -n $newest ]]; then
		for unit in "${MASKED_UNITS[@]}"; do
			if [[ -f "$newest/$unit" ]]; then
				install -m 644 "$newest/$unit" "$DISARM_UNIT_DIR/$unit"
				echo "Restored $unit from $newest"
			fi
		done
		rm -rf "$newest"
	fi

	systemctl --user daemon-reload
}
