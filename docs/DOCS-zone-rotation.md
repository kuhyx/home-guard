# Zone rotation

Mirrors steam-backlog-enforcer's "one game at a time": an ordered,
user-edited zone list, one zone assigned at a time, rotating to the next
only on a verified clear. Chosen over a single "whole home is clear" flag
because a photo of one tidy corner would trivially satisfy an all-or-nothing
claim — a smaller, verifiable unit is the whole point.

## Two files, two different shapes

**`.zone_list`** — forward-only edit history, ported from diet-guard's
`_meal_schedule_store.py` shape:

```json
{"v": 1, "e": {"2026-09-01": {"zones": ["desk", "kitchen counter", "entryway"], "t": "2026-09-01T08:00:00+02:00"}}}
```

Forward-only because editing the rotation (adding "garage", say) must not
retroactively change which zone an already-judged past slot was checked
against — the same reasoning diet-guard applies to editing a meal schedule
mid-week. `zone_list_for_day(entries, day)` picks the newest entry whose
`effective_from` is on or before `day`; no entry at all falls back to
`DEFAULT_ZONES`.

**`.zone_cursor`** — a plain pointer, *not* history:

```json
{"v": 1, "index": 1, "advanced_at": "2026-09-06T09:00:12+02:00", "last_slot": "2026-09-06:0900"}
```

`current_zone(now)` resolves `index % len(zone_list_for_day(..., today))` —
modulo against *today's* list, so a rotation that shrank since the cursor
last advanced still resolves to something valid instead of raising.
`advance(now, slot_key)` is called **only** by the accept pipeline on a
genuinely verified clear — never on a mere read, never speculatively — and
is idempotent per `slot_key`, so a poller that somehow fires the accept path
twice for the same evidence can't double-advance the rotation.

## What does *not* advance the cursor

Granting the escape hatch (`_escape_hatch.py`) satisfies the *slot* — the
lock releases, and today's check is logged as done — but never rotates the
zone. The zone was never actually verified clear, so it stays assigned and
still due next time. Only a genuine photo-verified `clear` entry
(`_accept.py::process_evidence`) advances the rotation.
