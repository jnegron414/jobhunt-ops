"""Daily Gmail sweep (READONLY): pipeline updates + recruiters owed a reply.

Two passes over the last few days of mail:
  1. Pipeline updates — threads mentioning a company with an active
     application, so interview scheduling / rejections / offers surface the
     morning they land even if unread.
  2. Recruiter radar — threads that look like recruiter outreach where the
     last message is NOT from you (i.e. you owe a reply), with days-waiting.
     Flagged threads are remembered (inbox_flags table) so the report shows
     how long each has been waiting and drops them once you reply.

Writes output/digests/inbox-YYYY-MM-DD.md and prints it. Readonly scope;
never sends, labels, or modifies anything. Cron-safe before OAuth setup
(email_sync.get_service exits quietly when consent is impossible).
"""
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
from email_sync import get_service  # noqa: E402  (same dir at runtime)

RECRUITER_QUERY = (
    'newer_than:3d -category:promotions -category:social '
    '(recruiter OR recruiting OR "talent" OR "opportunity" OR "reaching out" '
    'OR "your background" OR "open role" OR hiring OR "quick chat")'
)
# Senders that match the keywords but are never recruiters:
NOISE = ["linkedin.com", "udemymail.com", "amazon.com", "sofi", "citi.com",
         "rocketmortgage", "creditkarma", "piere.com", "newsletter",
         "no-reply", "noreply", "notifications@", "billing", "confirmation@",
         "receipt", "support@", "help@"]

FLAGS_SCHEMA = """CREATE TABLE IF NOT EXISTS inbox_flags (
    thread_id TEXT PRIMARY KEY, kind TEXT, first_seen TEXT, subject TEXT,
    sender TEXT, resolved_at TEXT
);"""


def headers(msg):
    return {h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])}


def sweep(svc, query, me, limit=25):
    """Return [(thread_id, subject, last_sender, last_from_me, last_ts)]."""
    resp = svc.users().threads().list(userId="me", q=query, maxResults=limit).execute()
    out = []
    for t in resp.get("threads", []):
        full = svc.users().threads().get(
            userId="me", id=t["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]).execute()
        msgs = full.get("messages", [])
        if not msgs:
            continue
        h_first, h_last = headers(msgs[0]), headers(msgs[-1])
        sender = h_last.get("from", "")
        out.append((t["id"], h_first.get("subject", "(no subject)"), sender,
                    me in sender, int(msgs[-1].get("internalDate", 0)) // 1000))
    return out


def main():
    svc = get_service()
    me = svc.users().getProfile(userId="me").execute()["emailAddress"]
    conn = config.get_db()
    conn.executescript(FLAGS_SCHEMA)
    today = date.today().isoformat()
    lines = [f"# Inbox watch — {today}", ""]

    # -- 1. pipeline updates -------------------------------------------------
    active = conn.execute(
        "SELECT DISTINCT company FROM applications WHERE stage IN ({})".format(
            ",".join("?" * len(config.ACTIVE_STAGES))), config.ACTIVE_STAGES).fetchall()
    updates = []
    for (company,) in [tuple(r) for r in active]:
        for tid, subj, sender, from_me, ts in sweep(
                svc, f'newer_than:3d "{company}"', me, limit=10):
            # Skip transactional mail from the company's own product (being a
            # CUSTOMER of a company you applied to floods this otherwise).
            if from_me or any(n in sender.lower() for n in NOISE):
                continue
            when = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M")
            updates.append(f"- **{company}**: {subj} — from {sender} ({when})")
    if updates:
        lines += ["## Pipeline updates (last 3d, not from you)"] + updates + [""]

    # -- 2. recruiter radar --------------------------------------------------
    owed = []
    for tid, subj, sender, from_me, ts in sweep(svc, RECRUITER_QUERY, me, limit=30):
        s = sender.lower()
        if any(n in s for n in NOISE):
            continue
        if from_me:
            conn.execute("UPDATE inbox_flags SET resolved_at=? "
                         "WHERE thread_id=? AND resolved_at IS NULL", (today, tid))
            continue
        row = conn.execute("SELECT first_seen FROM inbox_flags WHERE thread_id=?",
                           (tid,)).fetchone()
        if not row:
            conn.execute("INSERT INTO inbox_flags (thread_id, kind, first_seen, "
                         "subject, sender) VALUES (?,?,?,?,?)",
                         (tid, "recruiter", today, subj, sender))
            first = today
        else:
            first = row["first_seen"]
        waiting = (date.today() - date.fromisoformat(first)).days
        owed.append((waiting, f"- ({waiting}d waiting) {sender} — {subj}"))
    # Long-waiting flags that dropped out of the 3d window but were never resolved:
    for r in conn.execute("SELECT * FROM inbox_flags WHERE resolved_at IS NULL "
                          "AND kind='recruiter'").fetchall():
        if not any(r["subject"] in o for _, o in owed):
            waiting = (date.today() - date.fromisoformat(r["first_seen"])).days
            if waiting > 2:
                owed.append((waiting, f"- ({waiting}d waiting) {r['sender']} — {r['subject']}"))
    if owed:
        owed.sort(reverse=True)
        lines += ["## Recruiters owed a reply"] + [o for _, o in owed] + [""]

    if len(lines) <= 2:
        lines.append("Nothing needing attention today.")
    out = "\n".join(lines)
    dest = config.OUTPUT_DIR / "digests" / f"inbox-{today}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out + "\n")
    conn.commit()
    print(out)


if __name__ == "__main__":
    main()
