"""Shared config for jobhunt-ops. Edit the keyword lists and weights freely.

All personal data lives OUTSIDE this repo, under JOBHUNT_DATA_DIR
(default: ~/jobhunt-data). The repo never contains your data or output.
"""
import os
import sqlite3
from pathlib import Path

# Load .env (simple KEY=VALUE lines) without a dependency
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------- data layout
DATA_DIR = Path(os.environ.get("JOBHUNT_DATA_DIR", "~/jobhunt-data")).expanduser()
DB_PATH = DATA_DIR / "db" / "pipeline.sqlite3"
OUTPUT_DIR = DATA_DIR / "output"
TARGETS_FILE = DATA_DIR / "data" / "targets.yaml"
# Fallback so a fresh clone works before personal targets exist:
TARGETS_EXAMPLE = Path(__file__).parent / "targets.example.yaml"

# ---------------------------------------------------------------- filtering
TITLE_KEYWORDS = [
    "senior", "staff", "lead", "principal",
    "backend", "back-end", "platform", "infrastructure",
    "solution engineer", "solutions engineer", "sales engineer",
    "ai", "agent", "forward deployed",
]
LOCATION_KEYWORDS = ["new york", "nyc", "remote", "hybrid", "united states"]
# Titles containing any of these are dropped even if they match above
# (kills "Infrastructure Tax Lead" / "Communications Lead, Platform" noise):
NEGATIVE_TITLE_KEYWORDS = ["tax", "communications", "marketing", "recruit",
                           "counsel", "account executive", "people", "finance",
                           "accountant", "workplace", "physical security",
                           "product manager", "product design", "designer",
                           "sales manager", "account manager"]

# ---------------------------------------------------------------- scoring
FINTECH_KEYWORDS = ["payments", "banking", "plaid", "ledger", "lending",
                    "fintech", "ach", "card", "treasury"]
AI_KEYWORDS = ["llm", "agent", "claude", "anthropic", "openai", "gpt",
               "ml", "ai-native", "prompt"]
SENIOR_BACKEND_TITLES = ["backend", "back-end", "platform", "infrastructure"]
SENIORITY_MARKERS = ["senior", "staff", "lead", "principal"]
SOLUTION_TITLES = ["solution engineer", "solutions engineer", "sales engineer",
                   "forward deployed"]

SCORE_WEIGHTS = {
    "senior_backend_title": 30,
    "solution_engineer_title": 20,
    "fintech_description": 15,
    "ai_description": 15,
    "tier1_company": 10,
    "remote_or_nyc": 10,
}

# Recency: applications concentrate in a posting's first days, and older
# postings usually have candidates deep in the pipeline — applying early is
# the difference between being read and being archived. Recomputed at every
# scrape, so scores decay as postings age. (days_old_max, bonus) pairs,
# checked in order; postings older than the last threshold get RECENCY_STALE.
RECENCY_BONUSES = [(3, 20), (7, 15), (14, 8), (30, 3), (45, 0)]
RECENCY_STALE = -10

REQUEST_DELAY_SECONDS = 1.0

# ---------------------------------------------------------------- db helper
SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    location TEXT,
    dept TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    posted_at TEXT,
    raw_json TEXT,
    score INTEGER DEFAULT 0,
    status TEXT DEFAULT 'new',
    UNIQUE(company, url)
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executescript(TRACKER_SCHEMA)  # defined below; resolved at call time
    return conn


def load_targets():
    import yaml
    path = TARGETS_FILE if TARGETS_FILE.exists() else TARGETS_EXAMPLE
    if path is TARGETS_EXAMPLE:
        print(f"[config] {TARGETS_FILE} not found; using {path.name} (fill in your real targets)")
    with open(path) as f:
        return yaml.safe_load(f) or []

def extract_salary(raw):
    """Best-effort salary range from a posting's raw ATS JSON; '' if absent."""
    if not raw:
        return ""
    if isinstance(raw, str):  # raw JSON text: no structured fields, regex only
        raw = {"_text": raw}
    # Greenhouse boards API (content=true): pay_input_ranges
    for r in raw.get("pay_input_ranges") or []:
        lo, hi = r.get("min_cents"), r.get("max_cents")
        if lo and hi:
            return f"${lo // 100000}k-{hi // 100000}k"
    # Ashby: compensation.compensationTierSummary (a preformatted string)
    comp = raw.get("compensation") or {}
    if isinstance(comp, dict) and comp.get("compensationTierSummary"):
        return str(comp["compensationTierSummary"])
    # Lever: salaryRange {min, max}
    sr = raw.get("salaryRange") or {}
    if isinstance(sr, dict) and sr.get("min") and sr.get("max"):
        return f"${int(sr['min']) // 1000}k-{int(sr['max']) // 1000}k"
    # Fallback: pay-transparency laws put the range in the description text
    # far more often than orgs fill the structured fields (13/40 vs 0/40 in
    # a Sep 2026 sample). Match "$192,000 - $240,000" / "$150K–$180K".
    import json as _json
    import re as _re
    text = raw if isinstance(raw, str) else _json.dumps(raw)
    m = _re.search(
        r"\$(\d{2,3})(?:,(\d{3})|[Kk])\s*(?:[-–—−]|to)\s*\$?\s*(\d{2,3})(?:,(\d{3})|[Kk])",
        text)
    if m:
        lo = int(m.group(1)) if not m.group(2) else int(m.group(1) + m.group(2)) // 1000
        hi = int(m.group(3)) if not m.group(4) else int(m.group(3) + m.group(4)) // 1000
        if 40 <= lo < hi <= 900:  # sanity: plausible annual salary band in $k
            return f"${lo}k-{hi}k"
    return ""


def guess_level(title):
    t = (title or "").lower()
    for marker in ("principal", "staff", "senior", "lead"):
        if marker in t:
            return marker.capitalize()
    return ""


def load_do_not_apply():
    """Optional data/do_not_apply.yaml: [{name, level: hold|caution, why}].

    'hold' companies are suppressed from digests/shortlists entirely (e.g.
    current employer, conflict of interest, active business relationship);
    'caution' companies are shown but flagged. Returns {lowercase name:
    (level, why)}. Missing file = empty dict.
    """
    import yaml
    path = DATA_DIR / "data" / "do_not_apply.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        rows = yaml.safe_load(f) or []
    return {r["name"].strip().lower(): (r.get("level", "caution"), r.get("why", ""))
            for r in rows if r.get("name")}


GMAIL_CREDENTIALS_PATH = Path(os.environ.get(
    "GMAIL_CREDENTIALS_PATH", str(DATA_DIR / "gmail_credentials.json"))).expanduser()
GMAIL_TOKEN_PATH = DATA_DIR / "gmail_token.json"

STAGES = ["lead", "applied", "screen", "tech", "onsite", "offer",
          "closed_won", "closed_lost", "ghosted"]
ACTIVE_STAGES = ["lead", "applied", "screen", "tech", "onsite", "offer"]

TRACKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    url TEXT,
    source TEXT,
    stage TEXT DEFAULT 'lead',
    resume_variant TEXT,
    applied_at TEXT,
    updated_at TEXT,
    next_action TEXT,
    next_action_date TEXT,
    notes TEXT,
    jd_text TEXT,
    location TEXT,
    salary TEXT,
    level TEXT
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT, name TEXT, role TEXT, email TEXT, linkedin TEXT,
    relationship TEXT, last_touch TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER,
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    detail TEXT
);
"""
