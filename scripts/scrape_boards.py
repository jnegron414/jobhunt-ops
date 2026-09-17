"""Scrape public ATS job boards into the postings table.

Public JSON endpoints only — no auth, no HTML scraping, 1s delay between
companies, per-company failures logged and skipped.
"""
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402

UA = {"User-Agent": "jobhunt-ops/1.0 (personal job search tooling)"}


# ------------------------------------------------------------- ATS fetchers
def fetch_greenhouse(token):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    data = requests.get(url, headers=UA, timeout=20).json()
    if "jobs" not in data:
        raise ValueError(f"board not found or errored: {data}")
    for j in data["jobs"]:
        yield {
            "title": j.get("title", ""),
            "url": j.get("absolute_url", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "dept": ", ".join(d.get("name", "") for d in j.get("departments", []) or []),
            "description": j.get("content", "") or "",
            # Greenhouse's board API only exposes updated_at — a proxy for
            # posting date that resets on edits/reposts. Best available.
            "posted_at": _iso_date(j.get("updated_at")),
            "raw": j,
        }


def fetch_lever(token):
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    data = requests.get(url, headers=UA, timeout=20).json()
    if isinstance(data, dict):  # Lever returns {"ok": false, "error": ...} for bad tokens
        raise ValueError(f"board not found or errored: {data}")
    for j in data:
        cats = j.get("categories") or {}
        yield {
            "title": j.get("text", ""),
            "url": j.get("hostedUrl", ""),
            "location": cats.get("location", "") or "",
            "dept": cats.get("team", "") or "",
            "description": j.get("descriptionPlain", "") or "",
            "posted_at": _epoch_ms_date(j.get("createdAt")),
            "raw": j,
        }


def fetch_ashby(token):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    resp = requests.get(url, headers=UA, timeout=20)
    if resp.status_code != 200:
        raise ValueError(f"board not found (HTTP {resp.status_code})")
    for j in resp.json().get("jobs", []):
        yield {
            "title": j.get("title", ""),
            "url": j.get("jobUrl", "") or j.get("applyUrl", ""),
            "location": j.get("location", "") or "",
            "dept": j.get("department", "") or "",
            "description": j.get("descriptionPlain", "") or "",
            "posted_at": _iso_date(j.get("publishedAt")),
            "raw": j,
        }


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


# ----------------------------------------------------------- date helpers
def _iso_date(val):
    """'2026-09-12T08:11:00Z' (or +offset) -> '2026-09-12'; None if unparseable."""
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _epoch_ms_date(val):
    """Lever createdAt epoch-milliseconds -> 'YYYY-MM-DD'; None if unparseable."""
    if not val:
        return None
    try:
        return datetime.fromtimestamp(int(val) / 1000, tz=timezone.utc).date().isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def posting_age_days(posted_at, first_seen):
    """Days since the posting went up, falling back to when we first saw it."""
    basis = posted_at or first_seen
    try:
        return (date.today() - date.fromisoformat(basis)).days
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------ filter + score
def _contains_any(text, keywords):
    t = text.lower()
    return any(k in t for k in keywords)


def passes_filter(posting):
    if _contains_any(posting["title"], config.NEGATIVE_TITLE_KEYWORDS):
        return False
    title_ok = _contains_any(posting["title"], config.TITLE_KEYWORDS)
    loc = posting["location"] or ""
    # Empty location on remote-first boards is common; don't drop on it.
    loc_ok = (not loc) or _contains_any(loc, config.LOCATION_KEYWORDS)
    return title_ok and loc_ok


def score(posting, tier):
    w = config.SCORE_WEIGHTS
    title = posting["title"].lower()
    desc = (posting["description"] or "").lower()
    loc = (posting["location"] or "").lower()
    s = 0
    if _contains_any(title, config.SENIORITY_MARKERS) and _contains_any(title, config.SENIOR_BACKEND_TITLES):
        s += w["senior_backend_title"]
    if _contains_any(title, config.SOLUTION_TITLES):
        s += w["solution_engineer_title"]
    if _contains_any(desc, config.FINTECH_KEYWORDS):
        s += w["fintech_description"]
    if _contains_any(desc, config.AI_KEYWORDS):
        s += w["ai_description"]
    if tier == 1:
        s += w["tier1_company"]
    if _contains_any(loc, ["remote", "new york", "nyc"]):
        s += w["remote_or_nyc"]
    # Recency: fresh postings get a bonus, stale ones a penalty — applying in
    # a posting's first days is when a human actually reads the application.
    # first_seen may be None for a brand-new posting (not yet inserted): the
    # posting went up no earlier than today, so age 0.
    age = posting_age_days(posting.get("posted_at"), posting.get("first_seen")) or 0
    s += next((bonus for max_days, bonus in config.RECENCY_BONUSES if age <= max_days),
              config.RECENCY_STALE)
    return min(s, 100)


# ------------------------------------------------------------------- main
def main():
    targets = config.load_targets()
    today = date.today().isoformat()
    conn = config.get_db()
    inserted = updated = 0

    for t in targets:
        ats = t.get("ats", "manual")
        if ats == "manual":
            continue  # surfaced by digest.py as a weekly reminder
        fetcher = FETCHERS.get(ats)
        if not fetcher:
            print(f"[skip] {t['name']}: unknown ats '{ats}'")
            continue
        try:
            count = 0
            for p in fetcher(t["token"]):
                if not p["url"] or not passes_filter(p):
                    continue
                row = conn.execute(
                    "SELECT first_seen, posted_at FROM postings WHERE company=? AND url=?",
                    (t["name"], p["url"]),
                ).fetchone()
                if row:
                    p["first_seen"] = row["first_seen"]
                    # Keep the earliest posted_at we've recorded: Greenhouse's
                    # updated_at moves on every edit, which would fake freshness.
                    if row["posted_at"] and (not p["posted_at"] or row["posted_at"] < p["posted_at"]):
                        p["posted_at"] = row["posted_at"]
                s = score(p, t.get("tier", 3))
                if row:
                    conn.execute(
                        "UPDATE postings SET last_seen=?, score=?, title=?, location=?, "
                        "dept=?, posted_at=? WHERE company=? AND url=?",
                        (today, s, p["title"], p["location"], p["dept"], p["posted_at"],
                         t["name"], p["url"]),
                    )
                    updated += 1
                else:
                    conn.execute(
                        "INSERT INTO postings (company, title, url, location, dept, "
                        "first_seen, last_seen, posted_at, raw_json, score) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (t["name"], p["title"], p["url"], p["location"], p["dept"],
                         today, today, p["posted_at"], json.dumps(p["raw"])[:20000], s),
                    )
                    inserted += 1
                count += 1
            print(f"[ok]   {t['name']} ({ats}): {count} matching postings")
        except Exception as e:  # noqa: BLE001 — per-company isolation is the point
            print(f"[fail] {t['name']} ({ats}): {type(e).__name__}: {e}")
        time.sleep(config.REQUEST_DELAY_SECONDS)

    conn.commit()
    conn.close()
    print(f"[done] {inserted} new, {updated} still open")


if __name__ == "__main__":
    main()
