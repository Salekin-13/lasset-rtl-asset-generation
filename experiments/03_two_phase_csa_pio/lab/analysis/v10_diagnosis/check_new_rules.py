"""Checker for the new blind-spot rules (code only; prints a report, exit 1 on a BLOCKER).

  python -B check_new_rules.py <draft.json>
  draft.json: {"<rule id>": {"title": "...", "P1": "<Phase 1 block or null>", "P2": "<Phase 2 block or null>", ...}}

Per wording: words; slot labels Scope, Criteria, Outcome present and in that order in every block (Exceptions and
Evidence optional, Exceptions before Outcome, Evidence last); the block starts with "- <Title>." (or "- <Title> (a)."); the
project's prompt checks (meta_tools.check_prompt: corpus identifiers, numeric emission hints, comment reading).
Self-test first: a planted corpus name and a numeric hint are caught.
"""
import json
import re
import sys
from pathlib import Path

from diag_common import LAB, ROOT

for p in (ROOT / "src", ROOT / "assetgen_meta", ROOT / "bahavioral_patterns_of_assets"):
    sys.path.insert(0, str(p))
import labkit as K  # noqa: E402
import meta_tools as mt  # noqa: E402

NAMES = None


def names():
    global NAMES
    if NAMES is None:
        NAMES = K.corpus_names() | mt.corpus_names(str(ROOT))
    return NAMES


def check_text(rid, ph, t):
    probs = []
    blocks = re.split(r"\n(?=- )", t.strip())
    for b in blocks:
        if not re.match(r"- [A-Z][^\n.]*?(?: \([a-z]\))?\.\s*\n", b + "\n"):
            probs.append(f"BLOCKER block does not start with '- Title.': {b[:60]!r}")
        pos = [b.find(s) for s in ("Scope:", "Criteria", "Outcome:")]
        if any(p < 0 for p in pos) or pos != sorted(pos):
            probs.append(f"BLOCKER slots missing or out of order in {b[:40]!r}")
        if "Exceptions:" in b and not (b.find("Criteria") < b.find("Exceptions:") < b.find("Outcome:")):
            probs.append("BLOCKER Exceptions not between Criteria and Outcome")
        if "Evidence:" in b and b.find("Evidence:") < b.find("Outcome:"):
            probs.append("BLOCKER Evidence before Outcome")
    pr = mt.check_prompt(t, names(), f"{rid} {ph}")["problems"]
    probs += [f"BLOCKER prompt check: {p}" for p in pr]
    return probs


def main(path):
    sys.stdout.reconfigure(encoding="utf-8")
    plant = mt.check_prompt("Report at most 20 signals such as " + sorted(names())[0], names(), "plant")
    if len(plant["problems"]) < 2:
        print("self-test FAIL: planted problems not caught")
        sys.exit(1)
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    bad = 0
    for rid, x in d.items():
        for ph in ("P1", "P2"):
            t = x.get(ph)
            if not t:
                continue
            probs = check_text(rid, ph, t)
            bad += sum(p.startswith("BLOCKER") for p in probs)
            print(f"{rid} {ph}: {len(t.split())} words; " + ("ok" if not probs else "; ".join(probs)))
    print("RESULT:", "BLOCKERS" if bad else "clean")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1])
