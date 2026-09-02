---
description: Tailor resume + why-me + gap notes for a company's JD
---

# /tailor <company> <JD paste | file path | URL>

Arguments: $ARGUMENTS — first token is the company name; the rest is the job
description (pasted text, a local file path, or a URL to fetch).

Data dir: `$JOBHUNT_DATA_DIR` (default `~/jobhunt-data`; check `.env`).

## Steps

1. Read `data/resume_base.md`, `data/bullet_bank.md`, `data/war_stories.md`
   from the data dir. If `output/applications/<company>/profile.md` exists,
   read it too — it carries conclusions from earlier runs, and anything
   hand-edited by the human in it is authoritative over anything you generate.
2. Get the JD (fetch it if a URL). Extract: the top 6 requirements in the
   JD's own priority order, tech keywords, level signals, and whether the role
   is IC / solutions-engineer / lead flavored.
3. Write to `output/applications/<company>/`:
   - `resume_<company>.md` — start from resume_base; re-order and swap bullets
     (drawing on bullet_bank) so the selection mirrors the JD's priority
     order. HARD RULES: never invent or alter facts, numbers, or technologies
     not present in the data files; prefer bullets with metrics; max 2 pages;
     keep the existing section structure; no em dashes.
   - `whyme_<company>.md` — 120–150 words for application forms. Plain,
     confident, first person. References 2 specific true things about the
     company. No buzzword stacking, no em dashes.
   - `gap_notes.md` — honest list of JD requirements not strongly matched,
     and for each, which war story best covers it in an interview.
4. Create or append `output/applications/<company>/profile.md`: date, role,
   what was emphasized and why, the hook used, known gaps. Never rewrite or
   delete existing content in this file — append below it.
5. Run the claims gate and show its output:
   `.venv/bin/python scripts/verify_tailored.py output/applications/<company>/resume_<company>.md`
   (run from the repo root; the path above is inside the data dir). If it
   FLAGs anything, fix the resume and re-run until clean — a flagged number
   must be corrected to its sourced value or removed, never waved through.
6. End with a 5-line summary: what was emphasized, what was dropped, and why,
   so the human can sanity-check in 30 seconds.

## Conduct

- Assume-and-disclose: ask at most ONE clarifying question, and only if the
  answer would change the resume materially. Otherwise proceed on reasonable
  assumptions and list them in the closing summary.
- The gap notes are for the human, not the employer — be blunt there.
