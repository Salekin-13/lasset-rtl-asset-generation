"""(1) Repair row for v5g r0 bus's nesting slip: read the asset rows written inside points as if they were walk-level
rows (chain.to_assets on the repaired reply), score exactly; reported as its own row, strict stays main.
(2) Target compliance: every false positive the blind boundary test (boundary_result_compressed.json, either judge)
predicted a v5g sentence would remove: share of v5g runs where the element is still primary (of 3) vs share of v5f runs
(of 6). Read-only. Self-test: the unrepaired v5g r0 total equals compare_v5g.json (82 correct, 172 listed)."""
import json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB)); sys.path.insert(0, str(LAB.parents[2] / "src")); os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH, labkit as K
sys.stdout.reconfigure(encoding="utf-8")
import eval_assets as ea
with CH.at_root():
    refs = ea.load_refs()["gt"]
def ref(m):
    names = {n for (_, n) in CH.closed_names(m)}
    return [n for n, _ in refs[m] if n in names]
def score_assets(m, assets):
    listed = Counter(x["Asset RTL"] for x in assets); L = sum(listed.values()); T = 0
    for n in ref(m):
        if listed[n] > 0: listed[n] -= 1; T += 1
    return L, T
# (1) repair
run = CH.run_dir("two_phase_v5g", "gpt-5.6-luna", 0, "high")
tL = tT = 0
for m in CH.tuning_modules():
    a = json.loads((run / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
    L, T = score_assets(m, a); tL += L; tT += T
cmp = json.loads((HERE / "compare_v5g.json").read_text(encoding="utf-8"))["runs"]["v5g r0"]
print("self-test (unrepaired v5g r0 = compare_v5g):", "PASS" if (tL, tT) == (cmp["listed"], cmp["correct"]) else "FAIL", (tL, tT))
m = "neorv32_bus"
rec1 = json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8")); rec2 = json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
p1, p2 = K.parse_json(rec1["raw"]), K.parse_json(rec2["raw"])
fixed = json.loads(json.dumps(p2))
for w in fixed["Concept Walks"]:
    inner = []
    for p in w.get("Points", []):
        for key in ("Assets", "Not Reported"):
            if isinstance(p.get(key), list):
                (inner if key == "Assets" else w.setdefault("Not Reported", [])).extend(p.pop(key))
        if "No Primary Reason" in p and not w.get("No Primary Reason"):
            w["No Primary Reason"] = p.pop("No Primary Reason")
    seen = set(); rows = []
    for x in (w.get("Assets") or []) + inner:
        k = json.dumps(x, sort_keys=True)
        if k not in seen: seen.add(k); rows.append(x)
    w["Assets"] = rows
v1, _ = CH.from_format_phase1(p1, rec1["raw"])
concepts = CH.phase1_concepts(v1)
v2, _ = CH.from_format_phase2(fixed, "", [c.get("id") for c in concepts])
a = CH.to_assets(m, v2, concepts)["Assets"]
L, T = score_assets(m, a)
print(f"bus r0 repaired: listed {L}, correct {T} of {len(ref(m))} (strict: 0/0)")
print(f"v5g r0 with the repair row: listed {tL + L}, correct {tT + T}, precision {(tT + T) / (tL + L):.3f}, recall {(tT + T) / 109:.3f}")
# (2) target compliance
br = json.loads((LAB / "analysis/two_phase_v5f__gpt-5.6-luna__high__r0-r2/boundary/boundary_result_compressed.json").read_text(encoding="utf-8"))
targets = defaultdict(set)
for s in br["either"]["false positives removed"]:
    mm = re.match(r"r\d (\S+):(\S+) \[(.*)\]", s)
    targets[(mm.group(1), mm.group(2))] |= {x.strip(" '") for x in mm.group(3).split(",") if x.strip()}
def prim_share(v, reps, short, el):
    n = 0
    for r in reps:
        a = json.loads((CH.run_dir(v, "gpt-5.6-luna", r, "high") / "assets" / f"neorv32_{short}.json").read_text(encoding="utf-8"))["Assets"]
        n += any(x["Asset RTL"] == el for x in a)
    return n
per_rule = defaultdict(lambda: [0, 0, 0, 0])   # targets, v5g primary-runs, v5f primary-runs, targets gone in v5g
rows = []
for (short, el), rules in sorted(targets.items()):
    g = prim_share("two_phase_v5g", (0, 1, 2), short, el); f = prim_share("two_phase_v5f", range(6), short, el)
    rows.append((short, el, sorted(rules), f, g))
    for ru in rules:
        pr = per_rule[ru]; pr[0] += 1; pr[1] += g; pr[2] += f; pr[3] += g == 0
print(f"\ntarget false-positive elements (distinct): {len(rows)}; still primary, share of runs: v5g {sum(r[4] for r in rows)}/{3 * len(rows)} = {sum(r[4] for r in rows) / (3 * len(rows)):.2f}, v5f {sum(r[3] for r in rows)}/{6 * len(rows)} = {sum(r[3] for r in rows) / (6 * len(rows)):.2f}")
print("per rule: targets | primary-run share v5g (of 3 per target) vs v5f (of 6) | targets absent from every v5g run")
for ru, (n, g, f, gone) in sorted(per_rule.items(), key=lambda x: -x[1][0]):
    print(f"  {ru:6s} {n:3d} targets | v5g {g}/{3 * n} = {g / (3 * n):.2f} vs v5f {f}/{6 * n} = {f / (6 * n):.2f} | gone in v5g {gone}")
json.dump({"targets": rows, "per_rule": {k: v for k, v in per_rule.items()}}, open(HERE / "target_compliance.json", "w", encoding="utf-8"), indent=1)
