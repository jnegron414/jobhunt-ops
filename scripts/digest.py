"""Write the daily digest: new postings since the last digest, best first.

Silent (no file, exit 0) when there's nothing new. Mondays also remind you
about tier-1 companies that can't be scraped (ats: manual).
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402


def _age_label(p):
    """Posting age for a digest line: from posted_at (real posting date) when
    the ATS provided one, else from first_seen (our discovery date, marked ~)."""
    keys = p.keys()
    posted = p["posted_at"] if "posted_at" in keys else None
    basis, approx = (posted, "") if posted else (p["first_seen"], "~")
    days = (date.today() - datetime.strptime(basis, "%Y-%m-%d").date()).days
    return f"{approx}{days}d old"


def main():
    conn = config.get_db()
    today = date.today().isoformat()

    row = conn.execute("SELECT value FROM meta WHERE key='last_digest_at'").fetchone()
    last = row["value"] if row else "1970-01-01T00:00:00"

    # New = first seen after the date of the last digest run.
    new = conn.execute(
        "SELECT * FROM postings WHERE first_seen > ? ORDER BY score DESC, company",
        (last[:10],),
    ).fetchall()

    targets = config.load_targets()
    tier1 = [t["name"] for t in targets if t.get("tier", 3) == 1]
    manual_reminder = []
    if date.today().weekday() == 0:  # Monday
        manual_reminder = [t["name"] for t in targets
                           if t.get("ats") == "manual" and t.get("tier", 3) == 1]

    if not new and not manual_reminder:
        return  # nothing to say; no empty digests

    lines = [f"# Job digest — {today}", ""]

    if new:
        lines.append(f"## NEW ({len(new)})")
        for p in new:
            lines.append(f"- **{p['score']}** | {p['company']} — {p['title']} "
                         f"({p['location'] or 'location n/a'}) — {_age_label(p)} — {p['url']}")
        lines.append("")

    still = conn.execute(
        "SELECT p.* FROM postings p WHERE p.last_seen = ? AND p.first_seen <= ? "
        "AND p.company IN ({}) ORDER BY p.score DESC".format(",".join("?" * len(tier1))),
        [today, last[:10], *tier1],
    ).fetchall() if tier1 else []
    if still:
        lines.append(f"## STILL OPEN — tier 1 ({len(still)})")
        for p in still:
            lines.append(f"- **{p['score']}** | {p['company']} — {p['title']} "
                         f"({p['location'] or 'location n/a'}) — {_age_label(p)} — {p['url']}")
        lines.append("")

    if manual_reminder:
        lines.append("## CHECK MANUALLY (tier-1, no scrapable board)")
        for name in manual_reminder:
            lines.append(f"- {name}")
        lines.append("")

    out = "\n".join(lines)
    dest = config.OUTPUT_DIR / "digests" / f"{today}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out)
    print(out)

    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_digest_at', ?)",
                 (datetime.now().isoformat(timespec='seconds'),))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
