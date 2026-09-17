# jobhunt-ops

Job-search operations for one person: a deterministic scrape/track/digest
pipeline plus Claude Code commands for tailoring applications and interview
prep. CLI only, no web UI, no accounts.

All personal data (resume, career history, tracker DB, generated
applications) lives **outside this repo** in `$JOBHUNT_DATA_DIR`, so the repo
is code-only — safe to publish, and two people can run the same code against
completely separate data dirs.

**Hard constraints, by design:** the tool never sends email, never
auto-applies, and touches Gmail with readonly scope only. You review
everything; you click send.

## How it works

Two layers, deliberately separated (see `DECISIONS.md`):

1. **Deterministic layer** (Python, cron-able): scrapes the public JSON job
   boards (Greenhouse / Lever / Ashby) of companies you name, filters to
   roles matching your keywords, scores them, and writes a morning digest,
   a ranked apply-shortlist, and (optionally) two auto-updating Google
   Sheets. A SQLite tracker holds your application funnel, and a daily
   Gmail sweep surfaces application updates and recruiters you owe a reply.
2. **Intelligence layer** (Claude Code commands): `/tailor`, `/outreach`,
   `/brief` read your data dir and produce drafts — gated by a verifier that
   blocks any generated resume containing numbers not present in your own
   source files (no LLM-invented metrics survive).

### Scoring (why the digest is ordered the way it is)

Points for: senior backend title match, solutions-engineer title, fintech /
AI keywords in the description, tier-1 company, remote/NYC. Plus **recency**:
+20 if posted ≤3 days ago, decaying to −10 past 45 days — applications
concentrate in a posting's first days, and applying early is the difference
between being read and being archived. Scores recompute at every scrape, so
a posting's rank decays as it ages. Edit the keyword lists and
`SCORE_WEIGHTS` / `RECENCY_BONUSES` at the top of `config.py` to match your
own field and priorities — everything else is field-agnostic.

### Do-not-apply list and risk numbers

Some companies you shouldn't apply to even if they post great roles — a
current employer, an active business relationship, a conflict of interest,
or a direct competitor where a non-compete could bite. Declare them in
`data/do_not_apply.yaml` (`- {name, level, why}`):

- `hold` — never surfaced; suppressed from digests, shortlists, and sheets.
- `caution` — shown but flagged; check the reason before applying.
- `watch` — awareness only.

Every surfaced posting carries a risk number: **r0** clear, **r1** watch,
**r2** caution, **r3** suppressed. One gotcha the levels can't see:
**subsidiaries**. A posting's company name won't match its parent, so if a
parent company is on your list, grep the JD text ("wholly owned subsidiary
of") — the raw JSON is stored per posting for exactly this.

If the list lives in a spreadsheet you don't control (e.g. maintained by
someone else in Airtable), `scripts/sync_do_not_apply.py` regenerates the
YAML from it weekly — see its docstring; manual entries survive syncs via
the `extra:` block in `do_not_apply_source.yaml`.

## Setup (~15 minutes)

```bash
git clone <this repo> && cd jobhunt-ops
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # edit JOBHUNT_DATA_DIR if you want a custom location
mkdir -p ~/jobhunt-data/{data,db,output/digests,output/applications,output/briefs}
cp targets.example.yaml ~/jobhunt-data/data/targets.yaml
alias track='~/jobhunt-ops/.venv/bin/python ~/jobhunt-ops/scripts/tracker.py'  # add to shell rc
```

Then seed your data dir (`~/jobhunt-data/data/`). These files power
everything downstream — the better they are, the better `/tailor` is:

| File | What goes in it |
|---|---|
| `targets.yaml` | Companies you care about: `name`, `ats` (greenhouse/lever/ashby/manual), `token` (the slug in the company's careers URL, e.g. `boards.greenhouse.io/stripe` → `stripe`), `tier` (1 dream / 2 strong / 3 fine). Use `ats: manual` for companies with no scrapable board — tier-1 manuals surface as a Monday reminder. |
| `resume_base.md` | Your current full resume, markdown. `/tailor` cuts from this, never adds to it. |
| `career_record.md` | The long version of everything you've done — projects, metrics, incidents. This is the source of truth the claims gate verifies numbers against. Write it once, thoroughly. |
| `bullet_bank.md` | Resume bullets pre-written per theme (backend, scale, AI, etc.), so tailoring is selection, not generation. |
| `war_stories.md` | STAR-format incident/project stories for behavioral interviews. `/brief` draws from these. |
| `voice_samples.md` | 3–4 real emails you wrote, so `/outreach` drafts sound like you and not like an AI. |

### Writing `career_record.md` and `bullet_bank.md` (the two hours that matter)

Everything the tool generates is selection and compression from these two
files — it can never be better than they are. What works:

**career_record.md** — write it as an exhaustive private record, not a
resume. Nobody sees it but you and the tool, so optimize for completeness
and honesty, not polish:

- Go project by project through your whole tenure (walk your merged PRs,
  design docs, and tickets — memory alone misses half of it). For each:
  what was broken or missing, what you built, how you verified it worked,
  and what happened as a result.
- **Numbers, with sources.** Users, rows, requests/sec, latency before →
  after, dollars saved, deploy counts. Write down *where each number came
  from and the date you measured it* — the claims gate verifies tailored
  resumes against this file, and an interviewer will probe any number, so
  every one should be defensible on demand. Measure now, while you still
  have access; label estimates as estimates.
- **Incidents and failures are high-value material**, including the ones
  you caused. "My migration took prod down; here's the discipline I built
  afterwards" is a stronger interview answer than any success story. Record
  the timeline, your specific actions, and the lesson.
- **Be precise about attribution.** Note what teammates built and where
  your work ended. Inflated claims collapse under one follow-up question;
  precisely-scoped ones ("I owned the backend; a colleague built the
  mobile UI on top") survive anything.
- Include the boring-but-rare: on-call load, compliance work, cost
  reduction, migrations with zero downtime. These differentiate senior
  candidates more than feature lists do.

**bullet_bank.md** — distill the record into pre-written resume bullets,
grouped by theme (backend/architecture, scale/perf, incidents/reliability,
AI, security/compliance, leadership). Tailoring then becomes *choosing*
bullets per JD instead of writing under deadline. Each bullet: action →
scope → measured outcome, with every number traceable to the career
record. Write more than fit on any resume — 30-40 is right; a tailored
resume picks 10.

**war_stories.md** — for each major incident or project in the record,
a STAR-format story (situation, task, action, result + lesson). These are
your behavioral-interview answers, written once, calmly, with the numbers
in front of you — instead of reconstructed nervously in an interview.

## Daily loop

```bash
make morning   # scrape all boards + write digest + email sync + track today
```

The digest (`output/digests/YYYY-MM-DD.md`) lists new postings best-first
with age (`3d old`; `~3d` means age is from our discovery date because the
ATS didn't expose a posting date). Pick what's worth applying to, then:

```bash
track add "Stripe" "Senior Backend Engineer" --url <posting> --jd jd.txt  # JD text saved; postings go 404
track move 3 applied --note "referred by X"
track next 3 "follow up" --date 2026-09-24
track today        # every morning: due next-actions + stale applications
track ls --stale   # active apps with 7+ days of silence
track stats        # funnel counts, response rate, days-in-stage
```

Stages: `lead → applied → screen → tech → onsite → offer` and
`closed_won / closed_lost / ghosted`.

## Claude Code commands

Run these inside this repo with [Claude Code](https://claude.com/claude-code):

- **`/tailor <company> <JD paste|path|URL>`** — reads your resume, bullet
  bank, and war stories; produces `output/applications/<company>/` containing
  a tailored resume, a "why me" note, and honest gap notes (what the JD wants
  that you don't have — decide your story before they ask). Every generated
  resume is checked by `scripts/verify_tailored.py`: any number or claim not
  found in your source files fails the gate. Runs append conclusions to the
  company's `profile.md`; anything you hand-edit there is authoritative over
  future runs.
- **`/outreach <company|name> <context>`** — drafts recruiter/hiring-manager
  messages in your voice (from `voice_samples.md`). Drafts only — sending is
  yours.
- **`/brief <company>`** — pre-interview one-pager: recent company news,
  product direction, likely interview themes, which of your stories map to
  their stack.

## Optional

- **Cron:** `crontab crontab.example` installs the full schedule — daily
  7:30 scrape → digest → shortlist → sheet push, daily 7:45 inbox sweep,
  weekly do-not-apply sync (Mon), weekly funnel stats (Fri).
- **Google APIs (one OAuth client unlocks Sheets + Gmail):** in Google
  Cloud console enable the **Gmail API** and **Google Sheets API**, add
  yourself as a test user on the OAuth consent screen, create an OAuth
  client (under "Clients" in the new Google Auth Platform UI — type:
  Desktop app), and download its JSON to `GMAIL_CREDENTIALS_PATH` (see
  `.env`). Then run `sheet_sync.py` and `inbox_watch.py` once from a
  terminal — each opens a one-time browser consent; tokens cache in your
  data dir and cron takes over. Gmail access is readonly scope: the tool
  can suggest tracker updates from your mail (`email_sync.py --apply` to
  accept) but can never send, modify, or delete anything.
- **Google Sheets:** create two empty spreadsheets (or let your first CSVs
  seed them), put their IDs in `.env` as `SHEET_TO_APPLY_ID` and
  `SHEET_PIPELINE_ID`, and the daily cron rewrites them in place. The
  SQLite tracker is the source of truth — hand-edits to the sheets are
  overwritten; make changes via `track` instead.
- **Salary column:** filled automatically where the ATS publishes it —
  structured fields first, then pay-transparency ranges parsed from the
  JD text (catches roughly 40% of postings).
- **Personal noise filters:** senders the inbox sweep should never treat
  as signal (your bank, your employer, apps that share a name with a
  target company) go in `data/noise_senders.txt`, one substring per line —
  outside the repo, like all personal data.

## Sharing this with someone else

Nothing in this repo is specific to its author. A new user needs to: run
Setup, fill the six data files with their own material, and edit the keyword
lists in `config.py` for their field. The two most valuable hours are writing
`career_record.md` and `bullet_bank.md` — everything else compounds on those.
