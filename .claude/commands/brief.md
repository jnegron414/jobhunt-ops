---
description: One-page pre-interview brief for a company/stage
---

# /brief <company> [stage]

Arguments: $ARGUMENTS — company, and optionally the interview stage
(screen / tech / onsite). If stage is omitted, use the application's current
stage from the tracker.

Data dir: `$JOBHUNT_DATA_DIR` (default `~/jobhunt-data`; check `.env`).

## Steps

1. Read tracker state READ-ONLY (never write to the DB from this command):
   `sqlite3 $JOBHUNT_DATA_DIR/db/pipeline.sqlite3` — the application row for
   this company, its events, contacts, and which resume variant they saw.
   Read `output/applications/<company>/gap_notes.md` and `profile.md` if they
   exist (human edits in profile.md are authoritative).
2. Web-research the company, current-year sources preferred: product in one
   paragraph, funding/news from the last 12 months, engineering blog
   highlights, tech-stack signals from their own job posts, and interview
   format intel if findable. Cite nothing you could not point to.
3. Write `output/briefs/<company>/brief_<YYYY-MM-DD>.md`, ONE page max:
   - company snapshot (3-4 lines)
   - why-them-why-me (3 bullets, drawn from the same emphasis as the tailored
     materials so the story is consistent)
   - my prior touchpoints (from tracker events + contacts)
   - likely format for this stage
   - 3 gap areas with the counter-story for each (from gap_notes/war_stories)
   - 5 sharp questions to ask them (specific to this company, not generic)
4. Append one line to `profile.md`: date, stage briefed, anything new learned
   about the company worth carrying forward.

## Conduct

- Prep sheet, not essay. Bullets fine. One page is a hard cap.
- Assume-and-disclose: at most one clarifying question.
- If there is no tracker row for the company, still produce the brief from
  research + tailored materials, and note that the tracker has no history.
