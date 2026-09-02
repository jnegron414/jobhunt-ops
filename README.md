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

Phase 2 will add `scripts/tracker.py` (application tracker CLI) and
`scripts/email_sync.py` (Gmail readonly sync). Phase 3 adds the
`/tailor`, `/outreach`, `/brief` Claude Code commands.

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
4. (Phase 2) Create Gmail label `jobhunt` + OAuth desktop-app credentials in
   Google Cloud console; put the JSON path in `.env`. Readonly scope only.
5. Install the crontab.

## Design notes

See `DECISIONS.md` for why the system is split the way it is (deterministic
layer vs. LLM layer, why no auto-apply, why data lives outside the repo).
