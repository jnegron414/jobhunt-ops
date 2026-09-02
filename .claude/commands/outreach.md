---
description: Draft 3 outreach variants for a company contact, in my voice
---

# /outreach <company> <contact name + context>

Arguments: $ARGUMENTS — company first, then who the contact is and anything
known about the relationship ("worked with their SE team", "cold, eng manager
on the payments team", "friend of a friend").

Data dir: `$JOBHUNT_DATA_DIR` (default `~/jobhunt-data`; check `.env`).

## Steps

1. Read `data/voice_samples.md` and match that voice exactly: direct, warm,
   no corporate-speak, NO em dashes. Read the summary section of
   `data/career_record.md` for facts. If `output/applications/<company>/`
   contains tailored materials or `profile.md`, read them — reuse the same
   hook and emphasis so the story stays consistent across touchpoints
   (human-edited lines in profile.md are authoritative).
2. Write 3 variants, each ≤120 words, to
   `output/applications/<company>/outreach.md`:
   (a) warm intro ask, for someone I actually know;
   (b) cold note to a hiring manager or recruiter;
   (c) referral request that hands the person easy copy-paste language they
       can forward to the hiring manager.
3. Rules for every variant: exactly one specific hook (their product, stack,
   or recent news — must be true), exactly one clear ask, no "I hope this
   finds you well", no attachment mentions, no em dashes.
4. Append a line to `profile.md` (date, contact, variant intended, hook used).
5. Print the follow-up reminder command to run, e.g.:
   `track next <id> "follow up with <contact>" --date <+4 business days>`
   (if no application exists yet, print the `track add` first).

## Conduct

- Assume-and-disclose: at most one clarifying question; otherwise assume and
  note assumptions at the end.
- Never fabricate the relationship or the hook. If there is no true specific
  hook available, say so and ask for one instead of inventing.
