# jobhunt-ops

Personal job-search operations: a deterministic scraper/tracker pipeline plus
Claude Code commands for tailoring and interview prep. Single user, CLI only,
no web UI. All personal data lives OUTSIDE this repo (see below), so the repo
itself is code-only and safe to publish or clone.

**Hard constraints:** no auto-apply, no email sending, Gmail readonly-scope only.

## Layout

- This repo: code, `.claude/commands`, example config. Publishable.
- `$JOBHUNT_DATA_DIR` (default `~/jobhunt-data`): your resume, career record,
  targets, tracker DB, and all output. Never inside any repo.

## Setup

```bash
git clone <this repo> && cd jobhunt-ops
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                       # edit if your data dir differs
mkdir -p ~/jobhunt-data/{data,db,output/digests,output/applications,output/briefs}
cp targets.example.yaml ~/jobhunt-data/data/targets.yaml   # then edit
```

## Commands

| Command | What it does |
|---|---|
| `.venv/bin/python scripts/scrape_boards.py` | Scrape all targets' public ATS boards into the postings DB (filter + score) |
| `.venv/bin/python scripts/digest.py` | Write/print today's digest of new postings, best score first; silent if nothing new |
| `track today` | Morning view: due next-actions + stale active applications |
| `track add <co> <role> [--jd path]` | Add an application (store the JD text; postings go 404) |
| `track move <id> <stage> [--note]` | Advance/close an application (stages: lead applied screen tech onsite offer closed_won closed_lost ghosted) |
| `track note <id> "text"` / `track next <id> "action" --date YYYY-MM-DD` | Notes and next actions |
| `track ls [--stage --tier --stale]` | List applications (`--stale` = quiet 7+ days) |
| `track stats` | Funnel counts, response rate, avg days-in-stage |
| `.venv/bin/python scripts/email_sync.py [--apply]` | Gmail readonly sync of `jobhunt`-labeled threads; auto-advances only lead->applied, everything else is a suggestion until `--apply` |

Add the alias: `alias track='~/jobhunt-ops/.venv/bin/python ~/jobhunt-ops/scripts/tracker.py'`

Phase 3 adds the `/tailor`, `/outreach`, `/brief` Claude Code commands.

## Cron

```bash
crontab -e   # then paste the line from crontab.example (weekdays 7:30am)
```

## Manual setup (things only you can do)

0. Not an engineer? Edit the keyword lists at the top of `config.py` for your
   field — everything else is field-agnostic.
1. Edit `~/jobhunt-data/data/targets.yaml` — real companies, tiers, notes.
   Tokens are the slug in the company's careers URL (greenhouse/lever/ashby);
   use `ats: manual` when there's no scrapable board (tier-1 manual companies
   appear in Monday digests as a reminder).
2. Put your resume in `~/jobhunt-data/data/resume_base.md` and career record
   in `career_record.md`; extract `bullet_bank.md` + `war_stories.md` from it.
3. Paste 3–4 of your own emails into `~/jobhunt-data/data/voice_samples.md`.
4. Gmail sync: create the Gmail label `jobhunt` (swipe it onto job threads);
   in Google Cloud console create an OAuth client (type: Desktop app) with the
   Gmail API enabled, download the JSON to the path in `.env`
   (`GMAIL_CREDENTIALS_PATH`). First run of `email_sync.py` opens the browser
   consent screen once; the token caches in your data dir. Scope is
   gmail.readonly — the tool cannot send, modify, or delete mail.
5. Install the crontab.

## Design notes

See `DECISIONS.md` for why the system is split the way it is (deterministic
layer vs. LLM layer, why no auto-apply, why data lives outside the repo).
