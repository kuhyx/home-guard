"""Read-only MCP server: query gate status without ever granting anything.

Registered in ``.mcp.json``, run from a dedicated venv
(``scripts/setup_mcp.sh``) so the MCP SDK never has to be importable on the
systemd/CLI system-python path -- mirrors diet-guard's and leetcode-guard's
own MCP setup exactly.

Unlike diet-guard's MCP server (which has one gated ``log_meal`` write
tool), home-guard has **no write tool at all**. The whole point of this
gate is that a claim alone -- even one entered by an MCP client acting on
the user's behalf -- must never count; only a verified photo through the
phone's publish-then-echo path can grant a clear. ``test_mcp.py`` asserts
this invariant directly by checking every registered tool's annotations.

stdout is the JSON-RPC transport; nothing here may print to it. No secret
(the HMAC key, a challenge token, a photo) is ever returned by any tool.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Final

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from home_guard._gate import due_slots, gate_message
from home_guard._log import recent_entries
from home_guard._zone_cursor import current_zone
from home_guard._zone_list import load_zone_list_entries, zone_list_for_day

_READS_ONLY: Final = ToolAnnotations(
    read_only_hint=True, idempotent_hint=True, open_world_hint=False
)

mcp = MCPServer("home-guard")


@mcp.tool(title="Home Guard gate status", annotations=_READS_ONLY)
def get_status() -> dict[str, Any]:
    """Whether the gate is currently due, and for which zone."""
    now = datetime.now(tz=UTC).astimezone()
    slots = due_slots(now)
    return {
        "gate_is_due": bool(slots),
        "due_slots": list(slots),
        "current_zone": current_zone(now),
    }


@mcp.tool(title="Zone rotation", annotations=_READS_ONLY)
def get_zone_rotation() -> dict[str, Any]:
    """The zone list in force today, the current zone, and its edit history."""
    now = datetime.now(tz=UTC).astimezone()
    day = now.strftime("%Y-%m-%d")
    entries = load_zone_list_entries()
    return {
        "zones_today": list(zone_list_for_day(entries, day)),
        "current_zone": current_zone(now),
        "history": [
            {"effective_from": entry.effective_from, "zones": list(entry.zones)}
            for entry in entries
        ],
    }


@mcp.tool(title="Clear history", annotations=_READS_ONLY)
def get_clear_history(limit: int = 20) -> dict[str, Any]:
    """Recent clear/escape log entries -- photo paths, never photo bytes."""
    return {"entries": [dict(entry) for entry in recent_entries(limit=limit)]}


@mcp.tool(title="Why the gate is locked", annotations=_READS_ONLY)
def explain_lock() -> dict[str, Any]:
    """Human-facing explanation of the current gate state."""
    now = datetime.now(tz=UTC).astimezone()
    return {"message": gate_message(now), "gate_is_due": bool(due_slots(now))}


def main() -> None:  # pragma: no cover -- exercised by an MCP client, not pytest
    """Run the server over stdio."""
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":  # pragma: no cover
    main()
