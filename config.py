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
                           "accountant", "workplace", "physical security"]

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
    jd_text TEXT
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
