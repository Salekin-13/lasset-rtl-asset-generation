"""Blind adjudication pack: a fixed sample of the "mixed" cases of rule_consistency.json (a rule cited to exclude an
element in one v9 run, the element listed primary in another run). For each case: the rule's Phase 1 text (v9), the
element's closed-set facts and RTL lines, the row of the excluding run that cites the rule, and the primary row of the
kept run. No reference list, no score, no "reference" flag (leak check). Writes adjudication_cases.md and
adjudication_key.json (case id -> rule, module, element, split, reference flag; NOT given to the judges).

Sample: rules with 4+ mixed cases; per rule up to 4 cases, name-linked citations first, then alternating tuning /
held-out, then by module and element name (deterministic).

  python make_adjudication_pack.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rule_consistency as RC  # noqa: E402

T, CH, K, A = RC.T, RC.CH, RC.K, RC.A
V9 = RC.V9
LEAK = re.compile(r"\b(reference|ground truth|LAsset|TP|FP|correct find|findable|recall|precision)\b", re.I)


def rule_text(rule):
    p1 = (RC.LAB / "prompts" / V9 / "phase1.md").read_text(encoding="utf-8").split("\n")
    base = rule.split(" (")[0]
    for l in p1:
        if l.startswith(f"- {base}."):
            return "v9 phase1.md: " + l
    return {"2.6 bus record port bar": "common.md 2.6: A bus request record port (one that carries an address, data and a strobe) or bus response record port ..., or any field of one, is not a primary.",
            "Phase 2 synchronizer-stage bar": "phase2.md step 4: A synchronizer stage is not primary for any conceptual asset ...",
            "Phase 2 operand-copy bar": "phase2.md step 4: a register ... only holds that operand while the operation uses it ... never qualify as primary ...",
            "2.6 carrier sentence": "common.md 2.6: An internal element that only passes the value on between two of these ... carries it: a candidate secondary, not a primary."}.get(rule, rule)


def element_facts(m, n):
    facts = [(e, x) for (e, nn), x in CH.closed_names(m).items() if nn == n]
    lines = set()
    out = []
    for e, x in facts[:2]:
        d = {k: x[k] for k in ("port", "signal", "field", "direction", "type", "record type", "role in RTL", "counterparts") if k in x}
        out.append(f"{e}: {json.dumps(d, ensure_ascii=False)[:900]}")
        lines |= set(x.get("occurrence lines") or [])
    rtl = {int(mm.group(1)): l for l in CH.inputs(m)["rtl.txt"].splitlines() if (mm := re.match(r"\s*(\d+) \|", l))}
    show = sorted(lines)[:10]
    return out, [rtl[i] for i in show if i in rtl]


def rows_for(r, m, n, rule, rules):
    """Texts of run r that exclude n citing the rule, and n's primary row text if it is primary in r."""
    excl, prim = [], []
    raw = K.parse_json(T.load(V9, r, m, 1)["raw"])
    for x in raw.get("Not Kept") or []:
        t = json.dumps(x, ensure_ascii=False)
        if rule in RC.tag(t, rules):
            bn, bl = RC.linked(t, m)
            if n in bn or n in bl:
                excl.append("Phase 1 Not Kept: " + t[:700])
    p2 = T.load(V9, r, m, 2)["reply"] or {}
    for a in p2.get("structural assets") or []:
        if not isinstance(a, dict) or not (a.get("element") == n or n in CH.as_list(a.get("same role"))):
            continue
        j = str(a.get("justification") or a.get("reason") or "")
        if a.get("label") == "primary":
            prim.append(f"Phase 2 primary (concept {a.get('concept id')}): {j[:500]}")
        elif rule in RC.tag(j, rules):
            excl.append(f"Phase 2 {a.get('label')} (concept {a.get('concept id')}): {j[:500]}")
    for x in p2.get("not reported") or []:
        if isinstance(x, dict) and x.get("element") == n and rule in RC.tag(str(x.get("reason") or ""), rules):
            excl.append("Phase 2 not reported: " + str(x.get("reason"))[:500])
    return excl, prim


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rc = json.loads((HERE / "rule_consistency.json").read_text(encoding="utf-8"))
    cases = rc["B mixed cases"]
    rules = RC.rules_for(V9)
    by_rule = {}
    for c in cases:
        by_rule.setdefault(c["rule"], []).append(c)
    md = ["# Cases to judge (blind)\n",
          "Each case: one rule, one RTL element, and two runs of the same prompt on the same module. In one run the model",
          "excluded the element citing the rule; in another run it labelled the element primary. Judge from the rule's text",
          "and the RTL facts only.\n"]
    key = {}
    cid = 0
    for rule in sorted(by_rule, key=lambda r: -len(by_rule[r])):
        cs = by_rule[rule]
        if len(cs) < 4:
            continue
        name_first = []
        for c in cs:
            m, n = c["module"], c["element"]
            excl_r = c["excluded in runs"][0]
            ex, _ = rows_for(excl_r, m, n, rule, rules)
            named = any(T.has(n, e) for e in ex)
            name_first.append((not named, c["split"], m, n, c))
        name_first.sort(key=lambda x: (x[0], x[2], x[3]))
        tun = [x for x in name_first if x[1] == "tuning"]
        held = [x for x in name_first if x[1] == "held-out"]
        pick = []
        while len(pick) < 4 and (tun or held):
            for lst in (tun, held):
                if lst and len(pick) < 4:
                    pick.append(lst.pop(0))
        md.append(f"\n## Rule: {rule}\n\n{rule_text(rule)}\n")
        for _, s, m, n, c in pick:
            cid += 1
            facts, rtl = element_facts(m, n)
            r_ex, r_pr = c["excluded in runs"][0], c["primary in runs"][0]
            ex, _ = rows_for(r_ex, m, n, rule, rules)
            _, pr = rows_for(r_pr, m, n, rule, rules)
            md.append(f"\n### Case {cid}: module {m.replace('neorv32_', '')}, element {n}")
            md.append("Closed-set facts:\n" + "\n".join("- " + f for f in facts))
            if rtl:
                md.append("RTL lines where it occurs (first 10):\n```\n" + "\n".join(rtl) + "\n```")
            md.append(f"Run that excluded it (r{r_ex}):\n" + "\n".join("- " + e for e in ex[:2]))
            md.append(f"Run that labelled it primary (r{r_pr}):\n" + "\n".join("- " + p for p in pr[:2]))
            key[str(cid)] = {"rule": rule, "module": m, "element": n, "split": s, "reference": c["reference"]}
    text = "\n".join(md) + "\n"
    leak = LEAK.findall(text)
    (HERE / "adjudication_cases.md").write_text(text, encoding="utf-8")
    (HERE / "adjudication_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print(f"cases {cid}; rules {len({v['rule'] for v in key.values()})}; size {len(text):,}; leak check {'PASS' if not leak else 'FAIL ' + str(leak[:5])}")
    if leak:
        sys.exit(1)


if __name__ == "__main__":
    main()
