"""Build the split "tuning_v2" (user request 2026-10-14): the 15 tuning modules plus the held-out modules found
responsible for v7's drop from tuning to held-out (analysis/two_phase_v7__gpt-5.6-luna__high__r0-r2/heldout/
locate_degradation.py: ranked excess false positives and excess misses against v7's tuning level, the smallest set
covering 80% of the positive excess on either metric, positive in 2+ of 3 runs). The other held-out modules form
"heldout_v2".

Nothing in inputs/v1 or kit_data changes: the module files stay where they are (chain.module_dir finds a module in
tuning/ or heldout/), K.gt_modules() still gives the old 15 / 26 split, and the old compare scripts and the running
jobs are untouched. Later versions read this split through splits.py.

Written: tuning_v2.json (module lists, criterion, findable counts, v7's baseline on both new sets from its stored runs,
and the measured cost of one v7 run on each set from the stored usage).
Self-checks: the two lists are disjoint and cover the 41 reference modules; every module has rtl.txt, closed_set.json
and diagram.txt; the scorer's self-test (compare_v8.selftest); v7's baseline on the old 15 tuning modules is
92/89/86 of 146/158/131.

  python make_tuning_v2.py
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import cost_estimate as CE  # noqa: E402
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402

LOC = LAB / "analysis" / "two_phase_v7__gpt-5.6-luna__high__r0-r2" / "heldout" / "locate_degradation.json"
V, MODEL, EFF, REPS = "two_phase_v7", "gpt-5.6-luna", "high", (0, 1, 2)


def usd(u, P):
    if not u or u.get("in") is None:
        return 0.0
    cc = u.get("cached") or 0
    return ((u["in"] - cc) * P["in"] + cc * P["cached"] + (u.get("out") or 0) * P["out"]) / 1e6


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    old = K.gt_modules()
    loc = json.loads(LOC.read_text(encoding="utf-8"))
    moved = ["neorv32_" + m for m in loc["responsible modules (union)"]]
    tuning = old["tuning"] + [m for m in old["heldout"] if m in moved]
    heldout = [m for m in old["heldout"] if m not in moved]
    allm = old["tuning"] + old["heldout"]
    ok = (not set(tuning) & set(heldout)) and sorted(tuning + heldout) == sorted(allm) and len(allm) == 41 and len(moved) == len(set(moved))
    ok &= all((CH.module_dir(m) / f).exists() for m in allm for f in ("rtl.txt", "closed_set.json", "diagram.txt"))
    ref = C8.refs(sorted(allm))
    ok &= C8.selftest(ref)
    print("self-checks (disjoint, cover the 41 modules, inputs present, scorer self-test):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    P = CE.PRICES[MODEL]
    base = {}
    for name, mods in (("tuning (old 15)", old["tuning"]), ("tuning_v2", tuning), ("heldout_v2", heldout), ("heldout (old 26)", old["heldout"])):
        x = C8.runs(V, mods, ref)
        F = sum(len(ref[m]) for m in mods)
        T, L = sum(y["correct"] for y in x.values()), sum(y["listed"] for y in x.values())
        cost = sum(usd(json.loads((CH.run_dir(V, MODEL, r, EFF) / f"phase{p}" / f"{m}.json").read_text(encoding="utf-8")).get("usage"), P)
                   for r in REPS for m in mods for p in (1, 2)) / 3
        base[name] = {"modules": len(mods), "findable per run": F,
                      "v7 per run (correct, listed)": [(x[r]["correct"], x[r]["listed"]) for r in REPS],
                      "v7 pooled precision": f"{T}/{L} = {T / L:.3f}", "v7 pooled recall": f"{T}/{3 * F} = {T / (3 * F):.3f}",
                      "v7 cost per run, USD (stored usage)": round(cost, 2)}
        print(f"{name:18s} {len(mods):2d} modules, {F:3d} findable/run | v7 P {base[name]['v7 pooled precision']}, R {base[name]['v7 pooled recall']} | "
              f"USD {cost:.2f} per run")
    assert base["tuning (old 15)"]["v7 per run (correct, listed)"] == [(92, 146), (89, 158), (86, 131)]
    split = {
        "name": "tuning_v2", "built": "2026-10-14", "input version": "v1 (files unchanged; byte-identical to inputs/v1/manifest.json)",
        "request": "user 2026-10-14: add the held-out RTLs responsible for the drop to the tuning RTLs, as the tuning set for later versions",
        "criterion": "analysis/two_phase_v7__gpt-5.6-luna__high__r0-r2/heldout/locate_degradation.py: per held-out module, excess false "
                     "positives (FP - correct x (1-P)/P) and excess misses (missed - findable x 3 x (1-R)) against v7's tuning precision "
                     "267/435 and recall 267/327, pooled over r0-r2; the ranked smallest set covering 80% of the positive excess on either "
                     "metric, kept if positive in 2+ of 3 runs (80% is a chosen cut)",
        "moved from held-out to tuning": [m.replace("neorv32_", "") for m in moved],
        "tuning": tuning, "heldout": heldout,
        "v7 baseline (stored runs r0-r2)": base,
        "what it breaks": [
            "heldout_v2 was chosen by v7's own held-out results (the modules where v7 already does well), so it overstates "
            "generalization; it can show whether later rules hurt these modules, not whether they generalize to hard ones",
            "no CPU pipeline module with a large v7 error stays held out; a test of generalization to such modules needs new modules",
            "numbers on tuning_v2 are not comparable with the old 15-module numbers (109 findable per run); compare versions only on the same split",
            "v8's held-out run (all 26 modules) stays a clean test of v8, which was built before this split",
            "a run on tuning_v2 costs more than on the old 15 modules (see v7 cost per run)",
        ],
    }
    (HERE / "tuning_v2.json").write_text(json.dumps(split, indent=1), encoding="utf-8")
    print(f"written tuning_v2.json: tuning {len(tuning)} modules, heldout {len(heldout)} modules")


if __name__ == "__main__":
    main()
