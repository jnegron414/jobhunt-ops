"""Write output/apply-shortlist.md: open postings worth applying to, best first.

Unlike the digest (new postings only), this is the standing ranked list of
everything currently open, filtered through the do-not-apply list. Each line
carries a conflict-risk number for the company:

    r0 = clear (not on the do-not-apply list)
    r1 = watch  (on the list at a harmless level — awareness only)
    r2 = caution (check the reason before applying)
    r3 = hold — never shown; suppressed entirely, summarized at the bottom.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402

RISK = {"hold": 3, "caution": 2, "watch": 1}
TOP_N = 40


def main():
    dna = config.load_do_not_apply()
    conn = config.get_db()
    last = conn.execute("SELECT MAX(last_seen) m FROM postings").fetchone()["m"]
    rows = conn.execute(
        "SELECT * FROM postings WHERE last_seen=? ORDER BY score DESC, posted_at DESC",
        (last,),
    ).fetchall()

    kept, suppressed = [], set()
    for p in rows:
        entry = dna.get(p["company"].strip().lower())
        risk = RISK.get(entry[0], 0) if entry else 0
        if risk >= 3:
            suppressed.add(p["company"])
            continue
        kept.append((p, risk, entry[1] if entry else ""))

    lines = [
        f"# Apply shortlist — {date.today().isoformat()}",
        "",
        "Best score first; age from the ATS posting date — apply to fresh ones first.",
        "Risk: r0 clear · r1 watch (awareness) · r2 caution (check why) · r3 suppressed.",
        "",
    ]
    for p, risk, why in kept[:TOP_N]:
        basis = p["posted_at"] or p["first_seen"]
        age = (date.today() - date.fromisoformat(basis)).days
        risk_txt = f"r{risk}" + (f" ({why})" if risk else "")
        lines.append(
            f"- **{p['score']}** | {risk_txt} | {p['company']} — {p['title']} "
            f"({p['location'] or 'n/a'}) — {age}d old\n  {p['url']}"
        )
    if suppressed:
        lines += ["", f"_Suppressed (r3 hold): {', '.join(sorted(suppressed))}_"]

    out = config.OUTPUT_DIR / "apply-shortlist.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print(f"[shortlist] {out}: {min(len(kept), TOP_N)} shown of {len(kept)} eligible; "
          f"{len(suppressed)} companies suppressed")


if __name__ == "__main__":
    main()
