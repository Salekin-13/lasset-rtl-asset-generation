"""Verification units for the claims (claims_checked.json): claims grouped by the rule or prompt section their first
cited line belongs to (phase1 rule title; else the key phrase of a rule (attribute.RULE_KEYS) in the quote; else the
numbered section or step of the file), split into units of at most 5 claims; small clusters of the same kind (finds
or FPs) are packed together up to 4 claims. Writes verify/units/u<NN>.json and verify/units.json (unit -> claim ids).

  python make_units.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import attribute as A  # noqa: E402

LAB = A.LAB


def section(file, line):
    m = re.search(r"two_phase_(v\w+)/(common|phase1|phase2)\.md", file)
    if not m:
        return "?"
    v, fn = m.group(1), m.group(2)
    L = (LAB / "prompts" / f"two_phase_{v}" / f"{fn}.md").read_text(encoding="utf-8").splitlines()
    t = L[line - 1] if 0 < line <= len(L) else ""
    mm = re.match(r"- ([A-Z][A-Za-z -]*)\.", t)
    if fn == "phase1" and mm:
        return "rule: " + mm.group(1)
    for i in range(min(line, len(L)) - 1, -1, -1):
        h = re.match(r"^(\d\.\d+) ([A-Z].*)|^(\d)\. ([A-Z][a-z]+)", L[i])
        if h:
            return f"{fn} " + (h.group(1) or h.group(3) + ".") + " " + (h.group(2) or h.group(4))[:30]
    return fn + " top"


def rulekey(pl):
    q = pl["quote"].lower()
    for r, keys in A.RULE_KEYS.items():
        if any(k in q for k in keys) and " (" not in r:
            return "rule: " + r
    return section(pl["file"], pl["line"])


def main():
    d = json.loads((HERE / "claims_checked.json").read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for i, o in enumerate(d):
        c = o["claim"]
        g = "finds" if c["effect"] in ("lost finds", "gained finds", "persistent misses", "tuning contrast") else "FPs"
        k = rulekey(c["prompt_lines"][0]) if c["prompt_lines"] else "no line"
        groups[(g, k)].append(i)
    units, small = [], defaultdict(list)
    for (g, k), ids in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(ids) >= 3:
            n = -(-len(ids) // 5)
            size = -(-len(ids) // n)
            for j in range(0, len(ids), size):
                units.append({"kind": g, "topic": k, "claims": ids[j:j + size]})
        else:
            small[g].append((k, ids))
    for g, lst in small.items():
        cur = {"kind": g, "topic": [], "claims": []}
        for k, ids in lst:
            if len(cur["claims"]) + len(ids) > 4:
                units.append({**cur, "topic": "; ".join(cur["topic"])})
                cur = {"kind": g, "topic": [], "claims": []}
            cur["topic"].append(k)
            cur["claims"] += ids
        if cur["claims"]:
            units.append({**cur, "topic": "; ".join(cur["topic"])})
    out = HERE / "verify" / "units"
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for n, u in enumerate(units):
        uid = f"u{n:02d}"
        items = [{"claim index": i, "analyst": d[i]["analyst"], "claim": d[i]["claim"], "code check": d[i]["code check"]} for i in u["claims"]]
        (out / f"{uid}.json").write_text(json.dumps({"unit": uid, "kind": u["kind"], "topic": u["topic"], "items": items}, indent=1, ensure_ascii=False), encoding="utf-8")
        index.append({"unit": uid, "kind": u["kind"], "topic": u["topic"], "claims": [d[i]["claim"]["id"] for i in u["claims"]],
                      "claim indexes": u["claims"]})
    assert sorted(i for u in units for i in u["claims"]) == list(range(len(d))), "every claim in exactly one unit"
    (HERE / "verify" / "units.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"{len(d)} claims -> {len(units)} units (every claim in exactly one unit: PASS)")
    for u in index:
        print(f"  {u['unit']} {u['kind']:5s} {len(u['claims'])}  {u['topic'][:90]}")


if __name__ == "__main__":
    main()
