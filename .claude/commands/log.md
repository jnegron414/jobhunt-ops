---
description: Record a tracker event (add/move) as a pending file for Astro - the ONLY tracker write path on this machine
---

# /log <company> <stage> [role] [url] [note...]

Records an application event for Astro (the sole writer of the tracker DB) to
ingest. This command NEVER touches any SQLite database — the tracker lives on
Astro's machine and this Mac holds no authoritative copy.

## Steps

1. Parse: company and stage are required. Stage must be one of:
   lead, applied, screen, tech, onsite, offer, closed_won, closed_lost,
   ghosted. If the event creates a new application (no known prior row),
   action is "add" and role + url should be included; otherwise "move".
2. Check `~/jobhunt-state/rejected/` (after `git -C ~/jobhunt-state pull -q`):
   if any files are present, show their contents to the user before anything
   else — a previous event failed ingestion and may need re-emitting.
3. Write `~/jobhunt-state/pending/<UTC ISO8601 basic ts>-<company-slug>.json`:
   {"action": "add"|"move", "company": str, "role": str, "url": str,
    "stage": str, "note": str, "source": str, "salary": str, "location": str,
    "level": str, "ts": "<UTC ISO8601>"}
   Omit unknown optional fields rather than guessing. `ts` is event time
   (now, unless the user says when it happened — Astro orders by ts).
4. `git -C ~/jobhunt-state add -A && git -C ~/jobhunt-state commit -m "event: <company> -> <stage>" && git -C ~/jobhunt-state push`
5. Confirm to the user in one line: what was logged and that Astro will
   ingest it (tracker.json reflects it after Astro's next cycle).
