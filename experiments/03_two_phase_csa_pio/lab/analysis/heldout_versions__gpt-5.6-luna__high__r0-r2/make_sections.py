"""Inputs for the write-up: claims grouped into report sections, with their status (merge_verdicts.py), both checkers'
verdicts and corrections, and the code counts. Writes verify/sections/<section>.json; every claim lands in exactly one
section (refuted ones too, so each section can say what was ruled out).

  python make_sections.py
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
V = HERE / "verify"


def section(m):
    c = m["claim"]
    eff, topic = c["effect"], m["topic"]
    if eff in ("persistent FPs", "persistent misses"):
        return "S5_missing_rules"
    if eff in ("removed FPs",):
        return "S3_removed_fps"
    if eff in ("new FPs",):
        return "S4_new_fps"
    p1 = topic.startswith("rule:") or topic.startswith("phase1")
    return "S1_phase1_rules_and_finds" if p1 else "S2_phase2_common_and_finds"


def main():
    merged = json.loads((V / "merged.json").read_text(encoding="utf-8"))
    out = {}
    for m in merged:
        s = section(m)
        slim = {"check id": m["check id"], "status": m["status"], "analyst": m["analyst"],
                "claim": {k: m["claim"][k] for k in ("id", "step", "effect", "pattern", "elements", "prompt_lines", "intermediate_version",
                                                     "mechanism", "rule_scope", "confidence")},
                "reply evidence (verbatim, code-checked)": m["claim"]["reply_evidence"][:4],
                "code counts": {k: v for k, v in m["code check"].items() if "per version" in k},
                "verdicts": {l: {k: v[k] for k in ("verdict", "correction", "sub_step", "reason")} for l, v in m["verdicts"].items()}}
        out.setdefault(s, []).append(slim)
    (V / "sections").mkdir(exist_ok=True)
    for s, items in out.items():
        (V / "sections" / f"{s}.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{s}: {len(items)} claims {dict(Counter(i['status'] for i in items))}, {len(json.dumps(items)):,} chars")
    assert sum(len(v) for v in out.values()) == len(merged)


if __name__ == "__main__":
    main()
