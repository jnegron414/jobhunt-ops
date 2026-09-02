"""Deterministic claims-check gate for tailored resumes.

Every number/percentage in a tailored resume must appear in the source data
files (resume_base, bullet_bank, war_stories, career_record). Unsourced
numbers are hard FLAGs (exit 1). Capitalized terms not present in sources are
soft REVIEW items (exit 0) because proper-noun extraction is heuristic.

The LLM tailors; this script verifies. The model never gets to invent a number.

Usage: verify_tailored.py <tailored_resume.md>
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402

SOURCE_FILES = ["resume_base.md", "bullet_bank.md", "war_stories.md", "career_record.md"]

NUM_RE = re.compile(r"\$?\d[\d,.]*\s*(?:%|percent|[KMBkmb]\b|x\b|\+)?")
CAP_RE = re.compile(r"\b[A-Z][A-Za-z0-9+.#-]{2,}\b")
CAP_STOPLIST = {
    "The", "And", "For", "With", "From", "Into", "Over", "After", "Most",
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
    "Nov", "Dec", "January", "February", "March", "April", "June", "July",
    "August", "September", "October", "November", "December",
    "PROFESSIONAL", "SUMMARY", "TECHNICAL", "SKILLS", "EXPERIENCE",
    "EDUCATION", "Present", "Remote", "New", "York", "NY", "Brooklyn",
}


def norm_num(tok):
    return tok.replace(",", "").replace(" ", "").lower().rstrip("+")


def extract(path_text):
    nums = {norm_num(m.group()) for m in NUM_RE.finditer(path_text)}
    caps = {m.group() for m in CAP_RE.finditer(path_text)} - CAP_STOPLIST
    return nums, caps


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    tailored = Path(sys.argv[1]).read_text()

    src_text = ""
    for name in SOURCE_FILES:
        p = config.DATA_DIR / "data" / name
        if p.exists():
            src_text += "\n" + p.read_text()
    if not src_text:
        print("[verify] no source files found under data dir — cannot verify")
        sys.exit(2)

    t_nums, t_caps = extract(tailored)
    s_nums, s_caps = extract(src_text)
    s_caps_lower = {c.lower() for c in s_caps}

    flags = sorted(n for n in t_nums - s_nums if any(ch.isdigit() for ch in n))
    reviews = sorted(c for c in t_caps if c.lower() not in s_caps_lower)

    if flags:
        print("FLAG — numbers in the tailored resume with NO source in your data files:")
        for f in flags:
            print(f"  - {f}")
    if reviews:
        print("review — capitalized terms not found in sources (heuristic; check by eye):")
        for r in reviews:
            print(f"  - {r}")
    if not flags and not reviews:
        print("[verify] clean: every number and term is sourced.")
    sys.exit(1 if flags else 0)


if __name__ == "__main__":
    main()
