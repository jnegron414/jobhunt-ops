# JOBHUNT-OPS — Build Spec for Claude Code

## Architecture principle
Two layers, deliberately separated:
- **Deterministic layer (plain Python, no LLM):** scraper, tracker DB, email sync. Runs on cron, costs nothing, never hallucinates.
- **Intelligence layer (Claude Code commands):** tailoring and briefs, implemented as `.claude/commands/*.md` slash commands that read local files. Uses my existing Claude subscription — no API keys, no per-call cost.

Total build budget: **8 hours across all phases.** Ugly-but-working beats polished. No web UI anywhere — CLI and markdown output only. Single user: me.

## Amendment (2026-09-01, agreed before build)
All personal data and output live OUTSIDE the repo under `$JOBHUNT_DATA_DIR`
(default `~/jobhunt-data`), so the repo is code-only and publishable; anyone
can clone it and point it at their own data dir. The `data/`, `db/`, `output/`
paths below refer to that external directory. Additional agreed changes:
JD text stored at apply time (Phase 2); tier-1 `manual` targets surfaced as a
Monday digest reminder (Phase 1); `DECISIONS.md` maintained during the build.

## Repo layout
```
jobhunt-ops/                     # code only, publishable
├── SPEC.md
├── README.md
├── DECISIONS.md
├── config.py
├── targets.example.yaml
├── scripts/
│   ├── scrape_boards.py
│   ├── digest.py
│   ├── tracker.py               # CLI entrypoint (Phase 2)
│   └── email_sync.py            # Phase 2
├── .claude/commands/            # tailor.md, outreach.md, brief.md (Phase 3)
├── .env.example                 # JOBHUNT_DATA_DIR + Gmail creds path; gitignore .env
├── requirements.txt             # requests, pyyaml, click, google-api-python-client, google-auth-oauthlib
└── crontab.example

$JOBHUNT_DATA_DIR/               # personal, never in any repo
├── data/    career_record.md, resume_base.md, bullet_bank.md, war_stories.md,
│            targets.yaml, voice_samples.md
├── db/      pipeline.sqlite3
└── output/  digests/, applications/<company>/, briefs/<company>/
```

---

## PHASE 1 — Board scraper + daily digest (~2 hrs)

### targets.yaml schema
```yaml
- name: Plaid
  ats: lever            # greenhouse | lever | ashby | manual
  token: plaid          # board token/slug
  tier: 1               # 1 = dream, 2 = strong, 3 = fine
  notes: ""
```
Seeded with 15 rows across tiers; real targets filled by me.

### scrape_boards.py
- Public JSON endpoints, no auth, no HTML scraping:
  - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`
  - Lever: `https://api.lever.co/v0/postings/{token}?mode=json`
  - Ashby: `https://api.ashbyhq.com/posting-api/job-board/{token}`
- Normalize into `postings(id, company, title, url, location, dept, first_seen, last_seen, raw_json, score, status)`.
- Dedupe on (company, url); update `last_seen` on re-scrape; new rows get `first_seen = today`.
- Filter: title matches [senior, staff, lead, principal, backend, platform, infrastructure, solution(s) engineer, sales engineer, AI, agent] AND location matches [new york, nyc, remote, hybrid]. Keyword lists editable in `config.py`.
- Score 0–100: +30 senior backend/platform/infra title; +20 solution engineer; +15 fintech description keywords; +15 AI/agent keywords; +10 tier-1 company; +10 remote-or-NYC. Crude is fine.
- Per-company failures: log and continue. 1s delay between requests.

### digest.py
- Writes `output/digests/YYYY-MM-DD.md`: NEW since last run (score desc) then STILL OPEN (tier 1 only). Entry: score, company, title, location, url, days since first_seen. Mondays: tier-1 `manual` companies listed as CHECK MANUALLY.
- Prints to stdout; exits silently when nothing new.

**Acceptance:** scrape + digest produce a scored markdown digest from ≥3 real boards.

---

## PHASE 2 — Tracker CLI + Gmail sync (~2.5 hrs)

### tracker.py (click CLI)
Tables:
```
applications(id, company, role, url, source, stage, resume_variant,
             applied_at, updated_at, next_action, next_action_date, notes, jd_text)
contacts(id, company, name, role, email, linkedin, relationship, last_touch, notes)
events(id, application_id, ts, type, detail)
```
Stages: `lead → applied → screen → tech → onsite → offer → closed_won / closed_lost / ghosted`.

Commands: `track add <company> <role> [--url --source --stage --jd <path>]` ·
`track move <id> <stage> [--note]` · `track note <id> "<text>"` ·
`track next <id> "<action>" --date YYYY-MM-DD` · `track ls [--stage --tier --stale]`
(`--stale` = no activity 7+ days) · `track today` (morning command: next actions due +
stale warnings) · `track stats` (funnel counts, response rate, avg days-in-stage).

### email_sync.py
- Gmail API, **readonly scope only**. OAuth desktop flow, token cached locally, creds path in `.env`. Never request send/modify scopes.
- Convention: I label relevant threads `jobhunt` (optional `jobhunt/<company>`).
- On cron: fetch labeled threads updated since last sync, match to applications by from-domain or company name; confirmation language → stage `applied` if `lead`; scheduling language → flag NEEDS REPLY, suggest `screen`/`tech`; rejection language → suggest `closed_lost`.
- **Never auto-advance past `applied`; suggestions apply only with `--apply`.** Unmatched threads printed for manual `track add`. Everything logged to events.

**Acceptance:** label two real emails, run sync, see one auto-stage and one suggestion; `track today` is a coherent morning view.

---

## PHASE 3 — Claude Code commands (~2 hrs)

Markdown command files; no API calls; they read `$JOBHUNT_DATA_DIR` files and write to `$JOBHUNT_DATA_DIR/output/`.

### /tailor `<company> <JD paste|path|url>`
Read resume_base, bullet_bank, war_stories → extract top-6 JD requirements, keywords, level, IC/SE/lead → produce `applications/<company>/`: `resume_<company>.md` (bullets re-ordered/swapped to mirror JD priority; never invent facts/numbers/tech not in the data files; prefer metric bullets; max 2 pages; keep section structure), `whyme_<company>.md` (120–150 words, plain confident voice, references 2 specific things about the company), `gap_notes.md` (honest JD gaps + which war story covers each). End with a 5-line summary of what was emphasized.

### /outreach `<company> <contact + context>`
Read voice_samples (match my voice: direct, warm, no corporate-speak, no em dashes), career_record summary, tailored materials if present → 3 variants ≤120 words (warm intro ask / cold note to HM-recruiter / referral request with copy-paste forward text). One specific hook, one clear ask, no "hope this finds you well", no attachment mentions. Save to `applications/<company>/outreach.md` + print the `track next` reminder command.

### /brief `<company> [stage]`
Read tracker DB (read-only), events, contacts, resume variant sent → web-research company (product paragraph, 12-month funding/news, eng blog, stack signals, interview-format intel) → read gap_notes if present → `briefs/<company>/brief_<date>.md`, ≤1 page: snapshot / why-them-why-me / prior touchpoints / likely format this stage / 3 gaps with counter-stories / 5 sharp questions.

### Phase 3 additions (agreed 2026-09-02, patterns carried from prior work)
- `scripts/verify_tailored.py`: deterministic claims-check gate — every number,
  percentage, and technology term in a tailored resume must appear in
  resume_base/bullet_bank; unsourced claims print as FLAGs. /tailor runs it last.
- Shared per-company knowledge file `applications/<company>/profile.md`, read and
  appended by all three commands; human edits are terminal.
- Assume-and-disclose rule in all command prompts: at most one clarifying
  question, otherwise assume and list assumptions in the closing summary.

**Acceptance:** /tailor against one real JD + /brief for one company; outputs land correctly and pass a 30-second sanity check; verify_tailored flags a planted fake number.

---

## PHASE 4 — Glue (~30 min, optional)
- `make morning` → scrape + digest + email_sync + `track today`.
- Friday cron reminder to review `track stats`.

## Guardrails (enforced)
- No auto-apply, ever. No email sending. Gmail stays readonly.
- No personal data or `.env` in the repo: `data/`, `db/`, `output/` are external; gitignore is defense-in-depth.
- Over budget → cut scope (scoring nuance first), never extend time.
- Every script runs on a fresh clone with `pip install -r requirements.txt` + `.env`.

## Manual setup (me)
1. Personal `targets.yaml` in the data dir (started; fill to ~20).
2. 3–4 of my own emails into `voice_samples.md`.
3. Gmail label `jobhunt` + OAuth desktop credentials (Phase 2).
4. Install crontab.
