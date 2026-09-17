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
   roles matching your keywords, scores them, and writes a morning digest.
   A SQLite tracker holds your application funnel.
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

- **Cron:** `crontab -e`, paste the line from `crontab.example`
  (weekday-morning `make morning`).
- **Gmail sync** (`scripts/email_sync.py`): create a Gmail label `jobhunt`
  and apply it to job threads; in Google Cloud console create a Desktop-app
  OAuth client with the Gmail API enabled and download its JSON to
  `GMAIL_CREDENTIALS_PATH` (see `.env`). First run opens a one-time consent
  screen; the token caches in your data dir. Readonly scope — it can suggest
  tracker updates from your mail (`--apply` to accept) but cannot send,
  modify, or delete anything.

## Sharing this with someone else

Nothing in this repo is specific to its author. A new user needs to: run
Setup, fill the six data files with their own material, and edit the keyword
lists in `config.py` for their field. The two most valuable hours are writing
`career_record.md` and `bullet_bank.md` — everything else compounds on those.
