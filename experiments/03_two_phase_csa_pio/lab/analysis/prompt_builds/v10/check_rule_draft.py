"""Checker for v10 rule drafts (STRUCTURE_SPEC.md section 5). Code only; reads a draft JSON, prints a report.

  python check_rule_draft.py <draft.json>
  draft.json: {"<rule id>": {"P1_flat": "...", "P1_structured": "...", "P2_flat": "...", "P2_structured": "..."}}

Per rule and phase: words (v9 / flat / structured); words the structured text adds or drops relative to the flat text
(lower-cased word multiset; slot labels and numbering are not counted as added); slot labels present and in order
(Scope, Criteria, Exceptions, Outcome, then optional Evidence, per block); the project's prompt checks
(meta_tools.check_prompt: corpus identifiers, numeric emission hints, comment-reading) on both texts. "BLOCKER" marks a
failed project check or a missing slot. Self-test first: a planted corpus name and a numeric hint are caught, and a
reordered copy of a text adds and drops nothing.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
ROOT = LAB.parents[2]
for p in (LAB, ROOT / "src", ROOT / "assetgen_meta", ROOT / "bahavioral_patterns_of_assets"):
    sys.path.insert(0, str(p))
import labkit as K  # noqa: E402
import meta_tools as mt  # noqa: E402

V9 = json.loads((LAB / "analysis" / "rule_isolation_v9" / "rule_texts.json").read_text(encoding="utf-8"))
SLOTS = ["Scope:", "Criteria", "Outcome:"]                       # "Exceptions:" optional (lean form, 2026-10-15)
LABEL_WORDS = {"scope", "criteria", "all", "any", "of", "exceptions", "outcome", "evidence", "if", "then"}


def words(s):
    return len((s or "").split())


def toks(s):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9'\-]*", (s or "").lower().replace("’", "'"))
            if not re.fullmatch(r"\d", w)]


def slots_ok(s):
    """Each block (a line starting '- ' or a text without one) must hold Scope, Criteria, Exceptions, Outcome in order."""
    blocks = re.split(r"\n(?=\s*- )", s.strip()) if "\n" in s else [s]
    bad = []
    for b in blocks:
        pos = [b.find(x) for x in SLOTS]
        if min(pos) < 0:
            bad.append(f"missing {[x for x, p in zip(SLOTS, pos) if p < 0]} in block starting {b[:50]!r}")
        elif pos != sorted(pos):
            bad.append(f"slots out of order in block starting {b[:50]!r}")
        ex = b.find("Exceptions:")
        if ex >= 0 and not (pos[1] < ex < pos[2]):
            bad.append(f"Exceptions not between Criteria and Outcome in block starting {b[:50]!r}")
        ev = b.find("Evidence:")
        if ev >= 0 and ev < max(pos):
            bad.append(f"Evidence before Outcome in block starting {b[:50]!r}")
    return bad


def diff(flat, struct):
    a, b = Counter(toks(flat)), Counter(toks(struct))
    added = {w: n for w, n in (b - a).items() if w not in LABEL_WORDS}
    dropped = dict(a - b)
    return added, dropped


def report(draft, names):
    blockers = 0
    for rid, d in draft.items():
        title = V9.get(rid, {}).get("title", "?")
        print(f"\n== {rid} {title}")
        for ph in ("P1", "P2"):
            fl, st = d.get(f"{ph}_flat"), d.get(f"{ph}_structured")
            if fl is None and st is None:
                continue
            v9 = V9.get(rid, {}).get(ph)
            print(f"  {ph}: words v9 {words(v9)} | flat {words(fl)} | structured {words(st)}")
            for lab, text in (("flat", fl), ("structured", st)):
                if text:
                    pr = mt.check_prompt(text, names, f"{rid} {ph} {lab}")["problems"]
                    if pr:
                        blockers += 1
                        print(f"    BLOCKER prompt check ({lab}): {pr}")
            if st:
                for b in slots_ok(st):
                    blockers += 1
                    print(f"    BLOCKER slots: {b}")
                if fl:
                    add, drop = diff(fl, st)
                    print(f"    structured adds (beyond labels): {add or 'nothing'}")
                    print(f"    structured drops: {drop or 'nothing'}")
    print(f"\nblockers: {blockers}")
    return blockers


def selftest(names):
    t = V9["P1-18"]["P1"]
    plant = mt.check_prompt(t + " Report at most 20 such settings, as in " + sorted(names)[0] + ".", names, "plant")["problems"]
    parts = t.split(". ")
    re_ordered = ". ".join(parts[1:] + parts[:1])
    add, drop = diff(t, re_ordered)
    ok = len(plant) >= 2 and not add and not drop
    print("checker self-test (planted name and numeric hint caught; a reordered text adds and drops nothing):", "PASS" if ok else "FAIL")
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    names = K.corpus_names() | mt.corpus_names(str(ROOT))
    if not selftest(names):
        sys.exit(1)
    draft = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    report(draft, names)


if __name__ == "__main__":
    main()
