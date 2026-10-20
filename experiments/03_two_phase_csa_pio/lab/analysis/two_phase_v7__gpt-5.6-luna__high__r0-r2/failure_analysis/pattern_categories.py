"""Categories of the C1 patterns (the orchestrator's reading of the analysts' revised records, 2026-10-13; NOT checked
by any skeptic). Code sums the items. Split patterns list their items per category explicitly.
Self-check: every one of the 60 missed element-runs and 168 false-positive listings is counted exactly once."""
import json
from collections import Counter, defaultdict

FN = {  # category -> patterns (whole)
 "1. Phase 1 drops the concept: a bar applied beyond its text, or merged away": ["MA-P1", "MA-P2", "MA-P3", "MA-P4", "MA-P5", "MA-P6", "MA-P7", "MA-P8", "MA-P9", "MA-P10", "ME-P4"],
 "2. Phase 1 drops input ports the RTL never reads (the reference lists them)": ["MB-P1"],
 "3. Phase 1 keeps the concept but holds too few lines": ["MB-P3", "MB-P4", "MB-P5"],
 "4. Phase 2 names it but labels it secondary": ["ME-P1", "ME-P2", "ME-P3", "MC-P1", "MC-P2", "MO-P1"],
 "5. Phase 2 names the other end of an instance connection, or fields instead of the whole record": ["MC-P3", "MC-P4", "MC-P5"],
}
FN_SPLIT = {"MB-P2": {"4. Phase 2 names it but labels it secondary": ["M:cache:cache_i.sta_hit#1:r0", "M:cache:cache_i.sta_hit#1:r1", "M:cache:cache_i.sta_hit#1:r2"],
                      "5. Phase 2 names the other end of an instance connection, or fields instead of the whole record": ["M:cache:addr_i#1:r0"]}}
FP = {
 "A. A v7 rule already bars it, but the model did not apply the rule in that run": ["FP1-P1", "FP1-P2", "FP1-P4", "FP1-P5", "FP1-P6", "FP1-P8", "FP1-P9", "FP1-P11", "FP1-P12",
     "FPH-P1", "FPH-P2", "FPH-P14", "FPH-P3", "FPH-P15", "FPH-P4", "FPA-P1", "FPA-P3", "FPA-P4", "FPA-P15", "FPA-P5"],
 "B. The prompt was followed as written; the reference does not list the element": ["FP1-P3", "FP1-P10", "FPH-P5", "FPH-P16", "FPH-P6", "FPH-P7", "FPH-P8", "FPH-P17", "FPH-P9",
     "FPH-P10", "FPH-P13", "FPA-P6", "FPA-P7", "FPA-P8", "FPA-P9", "FPA-P16", "FPA-P10", "FPA-P11", "FPA-P14"],
 "C. Which end of an instance connection, or a pass-on rule read as a computation": ["FPH-P11", "FPA-P12", "FPA-P13", "FPH-P12"],
}
FP_SPLIT = {
 "FP1-P7": {"A. A v7 rule already bars it, but the model did not apply the rule in that run": ["F:cpu:neorv32_cpu:alu_cp_done:r0", "F:cpu:neorv32_cpu:alu_cp_done:r2"],
            "B. The prompt was followed as written; the reference does not list the element": "rest"},
 "FPA-P2": {"A. A v7 rule already bars it, but the model did not apply the rule in that run": ["F:cpu_cp_muldiv:neorv32_cpu_cp_muldiv:ctrl_i.ir_funct12:r1", "F:cpu_cp_muldiv:neorv32_cpu_cp_muldiv:ctrl_i.ir_funct3:r1", "F:cpu_cp_muldiv:neorv32_cpu_cp_muldiv:ctrl_i.ir_opcode:r1"],
            "B. The prompt was followed as written; the reference does not list the element": "rest"},
}
st = json.load(open("c1_status.json", encoding="utf-8"))
items = {p: v["items"] for p, v in st["patterns"].items()}
cls = {x["item"]: x["class"] for x in json.load(open("funnel_final.json", encoding="utf-8")) + json.load(open("fp_typed.json", encoding="utf-8"))}


def tally(spec, split, prefix):
    out, seen = defaultdict(list), Counter()
    for cat, ps in spec.items():
        for p in ps:
            out[cat] += items[p]
    for p, parts in split.items():
        taken = [i for v in parts.values() if v != "rest" for i in v]
        for cat, v in parts.items():
            out[cat] += [i for i in items[p] if i not in taken] if v == "rest" else v
    for v in out.values():
        for i in v:
            seen[i] += 1
    every = [i for p, v in items.items() if p.startswith(prefix) for i in v] if isinstance(prefix, str) else \
            [i for p, v in items.items() if p.split("-")[0] in prefix for i in v]
    ok = sorted(seen) == sorted(every) and all(n == 1 for n in seen.values())
    return out, ok, len(every)


fn, ok1, n1 = tally(FN, FN_SPLIT, ("MA", "MB", "MC", "ME", "MO"))
fp, ok2, n2 = tally(FP, FP_SPLIT, ("FP1", "FPH", "FPA"))
print(f"self-check: misses each counted once ({n1}): {ok1}; false positives each counted once ({n2}): {ok2}")
res = {}
for name, d, tot in (("misses", fn, n1), ("false positives", fp, n2)):
    print(f"\n{name} (of {tot}):")
    res[name] = {}
    for cat, v in d.items():
        c = Counter(cls[i] for i in v)
        runs = Counter(i.rsplit(":", 1)[1] for i in v)
        res[name][cat] = {"items": len(v), "by class": dict(c), "by run": dict(runs)}
        print(f"  {cat}: {len(v)} | consistent {c.get('consistent (3 of 3 runs)', 0)}, frequent {c.get('frequent (2 of 3)', 0)}, intermittent {c.get('intermittent (1 of 3)', 0)} | r0 {runs.get('r0', 0)} r1 {runs.get('r1', 0)} r2 {runs.get('r2', 0)}")
json.dump(res, open("pattern_categories.json", "w", encoding="utf-8"), indent=1)
