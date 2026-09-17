"""Export the pipeline + apply-shortlist to CSV, and push both to Google Sheets.

Always writes two CSVs under output/sheets/ (import them anywhere). If Google
Sheets access is configured, also pushes each into a pinned spreadsheet so the
sheets update in place daily from cron:

  .env:  SHEET_TO_APPLY_ID=<spreadsheet id>   # "Jobs To Apply" sheet
         SHEET_PIPELINE_ID=<spreadsheet id>   # "Pipeline" sheet

Auth reuses the same Google Cloud OAuth client as email_sync
(GMAIL_CREDENTIALS_PATH) with the spreadsheets scope; token caches in the
data dir (sheets_token.json). Without credentials this silently stops after
writing the CSVs, so it is cron-safe before setup.
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import os

import config  # noqa: E402

RISK = {"hold": 3, "caution": 2, "watch": 1}
STATUS_LABELS = {
    "lead": "Not Applied", "applied": "Applied", "screen": "First Call",
    "tech": "Technical", "onsite": "Onsite", "offer": "Offer",
    "closed_won": "Accepted", "closed_lost": "Closed", "ghosted": "Ghosted",
}
TOP_N = 40
SHEETS_TOKEN_PATH = config.DATA_DIR / "sheets_token.json"


def build_to_apply(conn, dna):
    last = conn.execute("SELECT MAX(last_seen) m FROM postings").fetchone()["m"]
    rows = conn.execute(
        "SELECT * FROM postings WHERE last_seen=? ORDER BY score DESC, posted_at DESC",
        (last,),
    ).fetchall()
    out = [["Score", "Risk", "Company", "Title", "Location", "Salary",
            "Posted", "Age (d)", "URL"]]
    for p in rows:
        entry = dna.get(p["company"].strip().lower())
        risk = RISK.get(entry[0], 0) if entry else 0
        if risk >= 3:
            continue
        basis = p["posted_at"] or p["first_seen"]
        age = (date.today() - date.fromisoformat(basis)).days
        try:
            salary = config.extract_salary(json.loads(p["raw_json"] or "null"))
        except (ValueError, TypeError):
            salary = ""
        risk_txt = f"r{risk}" + (f" ({entry[1]})" if risk else "")
        out.append([p["score"], risk_txt, p["company"], p["title"],
                    p["location"] or "", salary, basis, age, p["url"]])
        if len(out) > TOP_N:
            break
    return out


def build_pipeline(conn, dna):
    apps = conn.execute(
        "SELECT * FROM applications ORDER BY "
        "CASE WHEN stage IN ('closed_won','closed_lost','ghosted') THEN 1 ELSE 0 END, "
        "updated_at DESC"
    ).fetchall()
    out = [["Company", "Role", "Level", "Location", "Salary", "Status",
            "Date Applied", "Last Update", "Next Action", "Next Action Date",
            "Round History", "Risk", "Source", "URL", "Notes"]]
    for a in apps:
        events = conn.execute(
            "SELECT ts, detail FROM events WHERE application_id=? AND type='stage' "
            "ORDER BY ts", (a["id"],)).fetchall()
        history = "; ".join(f"{e['ts'][:10]}: {e['detail']}" for e in events)
        entry = dna.get(a["company"].strip().lower())
        risk = f"r{RISK.get(entry[0], 0)}" if entry else "r0"
        notes = conn.execute(
            "SELECT detail FROM events WHERE application_id=? AND type='note' "
            "ORDER BY ts DESC LIMIT 1", (a["id"],)).fetchone()
        out.append([
            a["company"], a["role"], a["level"] or "", a["location"] or "",
            a["salary"] or "", STATUS_LABELS.get(a["stage"], a["stage"]),
            (a["applied_at"] or "")[:10], (a["updated_at"] or "")[:10],
            a["next_action"] or "", a["next_action_date"] or "", history,
            risk, a["source"] or "", a["url"] or "",
            (notes["detail"] if notes else a["notes"]) or "",
        ])
    return out


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(rows)


def push_to_sheets(pairs):
    """pairs: [(spreadsheet_id, rows)]. Returns True if pushed."""
    if not config.GMAIL_CREDENTIALS_PATH.exists():
        return False
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = None
    if SHEETS_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(SHEETS_TOKEN_PATH), scopes)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not sys.stdin.isatty():
            return False  # cron: never try to open a consent browser
        flow = InstalledAppFlow.from_client_secrets_file(
            str(config.GMAIL_CREDENTIALS_PATH), scopes)
        creds = flow.run_local_server(port=0)
    SHEETS_TOKEN_PATH.write_text(creds.to_json())

    svc = build("sheets", "v4", credentials=creds)
    for sheet_id, rows in pairs:
        vals = [[str(c) for c in r] for r in rows]
        svc.spreadsheets().values().clear(
            spreadsheetId=sheet_id, range="A:Z").execute()
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range="A1",
            valueInputOption="RAW", body={"values": vals}).execute()
    return True


def main():
    dna = config.load_do_not_apply()
    conn = config.get_db()
    to_apply = build_to_apply(conn, dna)
    pipeline = build_pipeline(conn, dna)
    out_dir = config.OUTPUT_DIR / "sheets"
    write_csv(out_dir / "jobs_to_apply.csv", to_apply)
    write_csv(out_dir / "pipeline.csv", pipeline)
    print(f"[sheets] CSVs written to {out_dir} "
          f"({len(to_apply) - 1} to-apply rows, {len(pipeline) - 1} pipeline rows)")

    ids = (os.environ.get("SHEET_TO_APPLY_ID"), os.environ.get("SHEET_PIPELINE_ID"))
    if all(ids):
        pushed = push_to_sheets(list(zip(ids, [to_apply, pipeline])))
        print("[sheets] pushed to Google Sheets" if pushed
              else "[sheets] Google auth not ready; CSVs only "
                   "(run once interactively after creating the OAuth client)")
    else:
        print("[sheets] SHEET_TO_APPLY_ID / SHEET_PIPELINE_ID not set; CSVs only")


if __name__ == "__main__":
    main()
