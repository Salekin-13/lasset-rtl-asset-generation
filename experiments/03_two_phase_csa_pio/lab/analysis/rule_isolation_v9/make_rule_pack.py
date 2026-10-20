"""Rule pack for the rule-isolation diagnostics of two_phase_v9 (user request 2026-10-14: "Isolate each rule and run
separately on 41 modules ... find out if any phase 1 rule is in conflict with a phase 2 rule ... fix the wording").
Code only, read-only on the prompts; writes pack/ next to this file:
  pack/p1_rules.md       every Phase 1 rule bullet of v9 phase1.md ("- <Title>. ..."), numbered P1-01 ..., verbatim
  pack/p2_sentences.md   every sentence of v9 phase2.md step 4 ("4. Primary." line) and step 5, numbered S001 ...,
                         verbatim, with the file line
  pack/common_26_27.md   common.md 2.6 and 2.7 (the primary / secondary definitions), verbatim
  pack/index.json        the same in machine form (id -> text, line)
Self-check: joining the numbered sentences of each line gives the line back (nothing dropped); every Phase 1 bullet
title is unique.

  python make_rule_pack.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
V = LAB / "prompts" / "two_phase_v9"
SPL = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")


def main():
    p1 = (V / "phase1.md").read_text(encoding="utf-8").split("\n")
    p2 = (V / "phase2.md").read_text(encoding="utf-8").split("\n")
    com = (V / "common.md").read_text(encoding="utf-8").split("\n")
    rules = [(i + 1, l) for i, l in enumerate(p1) if re.match(r"- [A-Z][A-Za-z -]*\.", l)]
    titles = [re.match(r"- ([A-Z][A-Za-z -]*)\.", l).group(1) for _, l in rules]
    ok = len(titles) == len(set(titles))
    idx = {"p1": {}, "p2": {}, "common": {}}
    md1 = ["# Phase 1 rules of two_phase_v9 (phase1.md), verbatim\n"]
    for k, (ln, l) in enumerate(rules, 1):
        rid = f"P1-{k:02d}"
        idx["p1"][rid] = {"title": titles[k - 1], "line": ln, "text": l}
        md1.append(f"## {rid} {titles[k - 1]} (phase1.md:{ln})\n\n{l}\n")
    step_lines = [i for i, l in enumerate(p2) if l.startswith("4. Primary.") or l.startswith("5. Secondary.")]
    md2 = ["# Phase 2 step 4 (primary) and step 5 (secondary) of two_phase_v9 (phase2.md), one sentence per row\n"]
    n = 0
    for i in step_lines:
        sents = SPL.split(p2[i])
        ok &= " ".join(sents) == p2[i]
        md2.append(f"\n## phase2.md:{i + 1}\n")
        for s in sents:
            n += 1
            sid = f"S{n:03d}"
            idx["p2"][sid] = {"line": i + 1, "text": s}
            md2.append(f"- {sid}: {s}")
    a = next(i for i, l in enumerate(com) if l.startswith("2.6 "))
    b = next(i for i, l in enumerate(com) if l.startswith("2.8 "))
    idx["common"] = {"2.6-2.7": {"lines": [a + 1, b], "text": "\n".join(com[a:b])}}
    (HERE / "pack").mkdir(exist_ok=True)
    (HERE / "pack" / "p1_rules.md").write_text("\n".join(md1) + "\n", encoding="utf-8")
    (HERE / "pack" / "p2_sentences.md").write_text("\n".join(md2) + "\n", encoding="utf-8")
    (HERE / "pack" / "common_26_27.md").write_text("# common.md 2.6 and 2.7 (v9), verbatim\n\n" + "\n".join(com[a:b]) + "\n", encoding="utf-8")
    (HERE / "pack" / "index.json").write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Phase 1 rules {len(rules)}; Phase 2 step 4-5 sentences {n}; self-check {'PASS' if ok else 'FAIL'}")
    print("titles:", titles)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
