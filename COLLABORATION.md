# Collaboration contract: two agents, one job search

This deployment runs jobhunt-ops across two machines with strict ownership
boundaries, coordinated through a private state repo (`jobhunt-state`). The
generic pattern: a **deterministic agent** (always-on machine, here called
Astro) owns the pipeline and the database; an **intelligence agent** (Claude
Code on the user's workstation) owns judgment work — tailoring, outreach,
briefs. They never share a writable resource; everything crosses through git.

## Ownership

| Resource | Owner (sole writer) | Other side |
|---|---|---|
| Tracker DB (`db/pipeline.sqlite3`) | Astro | never reads or writes; consumes `tracker.json` |
| Scrape/digest/shortlist pipeline | Astro (daily 07:30 ET) | reads `postings.json`, `digests/`, `shortlist/` from state repo |
| Google Sheets (via `sheet_sync.py`) | Astro | none |
| Gmail scripted sweeps (readonly) | Astro (daily 07:45 ET) | ad-hoc user-prompted reads only |
| `output/applications/` drafts | Claude Code | none |
| Do-not-apply list (confidential source) | Claude Code's Mac (Mon 07:20 ET sync) | Astro reads the **hashed mirror** only |
| Tracker events | emitted by Claude Code via `/log` | ingested by Astro |

## Event handoff (`jobhunt-state` repo)

- Claude Code writes `pending/<UTC-ISO8601>-<company-slug>.json`:
  `{action: add|move, company, role, url, stage, note, source, salary,
  location, level, ts}`. Stages: lead, applied, screen, tech, onsite, offer,
  closed_won, closed_lost, ghosted.
- Astro validates **fail-closed** (unknown action/stage → `rejected/<file>.error.txt`,
  never guessed), ingests by `ts` order, dedups on `(company, url)`
  (an `add` for an existing pair becomes an update, never a duplicate),
  moves ingested files to `archive/`.
- Astro regenerates and pushes `tracker.json` (top-level `generated_at`,
  full application rows incl. next-action fields, per-application `history`,
  `recruiters_waiting` summary) after every ingest, inbox sweep, or
  chat-driven change.
- Claude Code pulls the state repo and reads `tracker.json` before `/brief`
  and `/outreach`, flags staleness past ~24h, and surfaces `rejected/`
  contents to the user before pushing new events.

## Confidential-list handoff (hashed membership check)

The do-not-apply list derives from confidential business information; its
plaintext never leaves the Mac and never enters any hosted repo. Astro only
needs membership checks, so the Monday sync publishes
`do_not_apply.hashed.json`:

- Secret: 64 lowercase hex chars (32 random bytes); the UTF-8 bytes of the
  hex string are the HMAC key. Delivered once via
  `secrets/hmac-secret.age` (age-encrypted to Astro's public key; ciphertext
  in the private repo is acceptable, plaintext never is).
- Entry: `HMAC_SHA256(secret, company_name.strip().lower()) → hold|caution|watch`.
  Reference: `hmac.new(secret.encode(), name.strip().lower().encode(), hashlib.sha256).hexdigest()`.
- Astro: hash each candidate company identically; `hold` → suppress
  entirely; `caution`/`watch` → surface with level flag only (no reason
  text exists on Astro's side, by design). No match → clear.
- Known limitation: subsidiary detection via JD text requires plaintext, so
  it stays on the Mac; known subsidiaries are added to the list by name so
  exact matching covers them. Anything the hash can't see, Astro can't
  suppress — accepted trade-off.

## Command-layer rules (this repo)

- `/log` is the **only** tracker write path on the workstation, and it writes
  pending files, never a database.
- `/tailor` ends by invoking `/log` on user-confirmed submission.
- `/brief` and `/outreach` begin with the state pull (see their preambles).
- The deterministic scripts remain in this repo as the code Astro runs;
  on the workstation they are retired at cutover except
  `sync_do_not_apply.py` (Monday, confidential source lives here).

## Cutover

Astro test-runs all jobs manually, then enables schedules. After the first
successful *scheduled* 07:30 run, the workstation disables its 07:30 morning
chain and 07:45 inbox launchd jobs, keeps only Monday 07:20 sync, and
archives (does not consult) its historical local DB copy.
