# Decision log

Written as the system was built. The point of this file: the code shows what
was built; this shows where the judgment calls were and why.

## 1. Two layers, and where the LLM boundary sits
The scraper, tracker, and email sync are plain Python on cron: they run every
morning unattended, cost nothing, and must never be wrong in creative ways.
An LLM adds nothing to "fetch JSON, dedupe, count days" except new failure
modes. The LLM layer (tailoring, outreach drafts, interview briefs) is where
judgment and language live, and it runs only when a human invokes it and
reviews the output. Rule of thumb applied throughout: **LLMs for judgment and
language, deterministic code for facts, state, and anything that runs
unattended.**

## 2. No auto-apply, no email sending, Gmail readonly (hard constraints)
Not preferences. Auto-apply produces low-quality volume and reputational risk
with exactly the companies I care about; anything that sends email can
embarrass me at machine speed. The Gmail integration requests the readonly
scope only, so even a bug cannot send, modify, or delete anything. The email
sync additionally never auto-advances an application past "applied" — stage
changes beyond that are suggestions requiring an explicit `--apply` flag,
because a false "rejected" inference that silently closes an application is
worse than no automation.

## 3. Personal data lives outside the repo entirely
Original plan was gitignore discipline; changed to physical separation
(`$JOBHUNT_DATA_DIR`, default `~/jobhunt-data`). A public repo protected by
gitignore is one `git add -f` from leaking a career record, application
tracker, and per-company gap analyses. With data outside the tree, the repo is
publishable-by-construction, and anyone can clone it and point it at their own
data directory. Gitignore still covers `data/`, `db/`, `output/`, `.env` as
defense in depth.

## 4. Crude scoring, on purpose
The score is additive keyword matching, ~0–100. It exists to sort a morning
digest, not to make decisions — the human reads the list. Anything smarter
(embeddings, LLM ranking) would add cost and opacity to a step whose failure
mode ("a good job sorted 5 rows lower") is nearly free. The one refinement
worth its cost, found on the first real run: a negative-keyword list, because
"Infrastructure Tax Lead" title-matches "infrastructure" + "lead" and scored
80 before "Staff Software Engineer, Backend" variants.

## 5. Boards fail loudly, companies fail independently
The spec's own example tokens turned out not to exist (Plaid is on Ashby, not
Lever). Invalid board tokens initially looked identical to "no matching
roles" — a silent zero. Fetchers now raise on error payloads so a dead token
shows as `[fail]` in cron output, while each company is wrapped in its own
try/except so one dead board never kills the run.

## 6. SQLite, one file, no ORM
Single user, hundreds of rows, cron cadence. A schema string and `sqlite3`
beats any framework here; the DB is disposable and rebuildable from a scrape.

## 7. JDs are stored at apply time (Phase 2)
Postings get taken down constantly, and interview prep needs the original JD
weeks later. `applications.jd_text` captures it when I apply, because by
brief-time the URL is often a 404.
