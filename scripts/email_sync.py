"""Gmail sync — READONLY scope, suggestion-first.

Convention: apply the Gmail label `jobhunt` to relevant threads. This script
fetches labeled threads updated since the last sync and matches them to
applications. It auto-advances ONLY lead -> applied on confirmation language;
everything else prints as a suggestion and is applied only with --apply.
It can never send, modify, or delete mail (scope makes it impossible).
"""
import base64
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # never widen

CONFIRM = ["application received", "thanks for applying", "thank you for applying",
           "we received your application", "application has been received"]
SCHEDULING = ["schedule", "availability", "calendly", "cal.com", "book a time",
              "set up a call", "set up some time"]
REJECT = ["unfortunately", "other candidates", "not moving forward",
          "not be moving forward", "decided to pursue", "position has been filled"]


def get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if config.GMAIL_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(config.GMAIL_TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not config.GMAIL_CREDENTIALS_PATH.exists():
                print(f"[email_sync] no Gmail credentials at {config.GMAIL_CREDENTIALS_PATH} — "
                      "see README 'Manual setup'. Skipping.")
                sys.exit(0)
            if not sys.stdin.isatty():
                print("[email_sync] Gmail consent needed but not interactive (cron); "
                      "run once from a terminal. Skipping.")
                sys.exit(0)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.GMAIL_CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        config.GMAIL_TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def thread_text(svc, thread_id):
    t = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
    subject = sender = ""
    body_parts = []
    for msg in t.get("messages", []):
        for h in msg.get("payload", {}).get("headers", []):
            if h["name"].lower() == "subject" and not subject:
                subject = h["value"]
            if h["name"].lower() == "from":
                sender = h["value"]
        stack = [msg.get("payload", {})]
        while stack:
            part = stack.pop()
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                body_parts.append(base64.urlsafe_b64decode(part["body"]["data"]).decode(errors="ignore"))
            stack.extend(part.get("parts", []) or [])
    return subject, sender, "\n".join(body_parts)[:5000]


def match_application(conn, subject, sender, body):
    domain = ""
    m = re.search(r"@([\w.-]+)", sender)
    if m:
        domain = m.group(1).lower()
    hay = f"{subject} {body}".lower()
    for app in conn.execute("SELECT * FROM applications WHERE stage IN ({})".format(
            ",".join("?" * len(config.ACTIVE_STAGES))), config.ACTIVE_STAGES).fetchall():
        c = app["company"].lower()
        key = c.replace(" ", "")
        if key in domain or c in hay:
            return app
    return None


def classify(subject, body):
    hay = f"{subject} {body}".lower()
    if any(k in hay for k in REJECT):
        return "reject"
    if any(k in hay for k in SCHEDULING):
        return "scheduling"
    if any(k in hay for k in CONFIRM):
        return "confirm"
    return "other"


def main():
    apply_suggestions = "--apply" in sys.argv
    svc = get_service()
    conn = config.get_db()
    row = conn.execute("SELECT value FROM meta WHERE key='last_email_sync'").fetchone()
    last = row["value"] if row else "1970-01-01"
    after = int(datetime.fromisoformat(last).timestamp())

    resp = svc.users().threads().list(
        userId="me", q=f"label:jobhunt after:{after}", maxResults=50).execute()
    threads = resp.get("threads", [])
    if not threads:
        print("[email_sync] nothing new under label:jobhunt")
    for th in threads:
        subject, sender, body = thread_text(svc, th["id"])
        app = match_application(conn, subject, sender, body)
        kind = classify(subject, body)
        tag = f"'{subject[:60]}' from {sender[:40]}"
        if not app:
            print(f"[unmatched] {tag} — add manually: track add \"<Company>\" \"<Role>\"")
            continue
        if kind == "confirm" and app["stage"] == "lead":
            conn.execute("UPDATE applications SET stage='applied', applied_at=?, updated_at=? WHERE id=?",
                         (datetime.now().isoformat(timespec='seconds'),) * 2 + (app["id"],))
            conn.execute("INSERT INTO events (application_id, ts, type, detail) VALUES (?,?,?,?)",
                         (app["id"], datetime.now().isoformat(timespec='seconds'),
                          "email_sync", f"auto: lead -> applied ({subject[:80]})"))
            print(f"[auto] [{app['id']}] {app['company']}: lead -> applied — {tag}")
        elif kind == "scheduling":
            suggestion = "screen" if app["stage"] in ("lead", "applied") else "tech"
            if apply_suggestions:
                conn.execute("UPDATE applications SET stage=?, updated_at=? WHERE id=?",
                             (suggestion, datetime.now().isoformat(timespec='seconds'), app["id"]))
                print(f"[applied-suggestion] [{app['id']}] {app['company']} -> {suggestion} — {tag}")
            else:
                print(f"[NEEDS REPLY] [{app['id']}] {app['company']}: scheduling language — "
                      f"suggest stage {suggestion} (rerun with --apply) — {tag}")
            conn.execute("INSERT INTO events (application_id, ts, type, detail) VALUES (?,?,?,?)",
                         (app["id"], datetime.now().isoformat(timespec='seconds'),
                          "email_sync", f"scheduling detected: {subject[:80]}"))
        elif kind == "reject":
            if apply_suggestions:
                conn.execute("UPDATE applications SET stage='closed_lost', updated_at=? WHERE id=?",
                             (datetime.now().isoformat(timespec='seconds'), app["id"]))
                print(f"[applied-suggestion] [{app['id']}] {app['company']} -> closed_lost — {tag}")
            else:
                print(f"[suggest] [{app['id']}] {app['company']}: rejection language — "
                      f"suggest closed_lost (rerun with --apply) — {tag}")
            conn.execute("INSERT INTO events (application_id, ts, type, detail) VALUES (?,?,?,?)",
                         (app["id"], datetime.now().isoformat(timespec='seconds'),
                          "email_sync", f"rejection detected: {subject[:80]}"))
        else:
            print(f"[seen] [{app['id']}] {app['company']} — {tag}")

    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_email_sync', ?)",
                 (datetime.now().isoformat(timespec='seconds'),))
    conn.commit()


if __name__ == "__main__":
    main()
