"""Per module and run: correct / listed (exact scorer), v5g r0-r2 vs v5f r0-r5; plus Phase 1 concept counts and
Phase 2 walks with no primary. Read-only on stored files. Self-test: column sums equal compare_v5g.json per run."""
import json, os, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB)); sys.path.insert(0, str(LAB.parents[2] / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH, labkit as K
sys.stdout.reconfigure(encoding="utf-8")
import eval_assets as ea
with CH.at_root():
    refs = ea.load_refs()["gt"]
RUNS = [("v5g", "two_phase_v5g", r) for r in (0, 1, 2)] + [("v5f", "two_phase_v5f", r) for r in range(6)]
cmp = json.loads((HERE / "compare_v5g.json").read_text(encoding="utf-8"))["runs"]
tot = Counter(); rows = []
for m in CH.tuning_modules():
    names = {n for (_, n) in CH.closed_names(m)}
    ref = [n for n, _ in refs[m] if n in names]
    cells = []
    for k, v, r in RUNS:
        run = CH.run_dir(v, "gpt-5.6-luna", r, "high")
        listed = Counter(x["Asset RTL"] for x in json.loads((run / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"])
        L = sum(listed.values()); T = 0
        for n in ref:
            if listed[n] > 0: listed[n] -= 1; T += 1
        p1 = K.parse_json(json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
        p2 = K.parse_json(json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
        nc = len(p1.get("Conceptual Assets", []))
        nop = sum(1 for w in p2.get("Concept Walks", []) if isinstance(w, dict) and not any(isinstance(a, dict) and a.get("Label") == "primary" for a in (w.get("Assets") or [])))
        cells.append(f"{T}/{L} c{nc} n{nop}")
        tot[(k, r, "T")] += T; tot[(k, r, "L")] += L
    rows.append((m.replace("neorv32_", ""), len(ref), cells))
print("cell = correct/listed, c = Phase 1 concepts, n = Phase 2 walks with no primary")
print(f"{'module':14s} {'ref':>3s}  " + "  ".join(f"{k} r{r}".ljust(14) for k, _, r in RUNS))
for m, nref, cells in rows:
    print(f"{m:14s} {nref:3d}  " + "  ".join(c.ljust(14) for c in cells))
ok = all((tot[(k, r, "T")], tot[(k, r, "L")]) == (cmp[f"{k} r{r}"]["correct"], cmp[f"{k} r{r}"]["listed"]) for k, _, r in RUNS)
print("self-test (sums = compare_v5g.json):", "PASS" if ok else "FAIL")
