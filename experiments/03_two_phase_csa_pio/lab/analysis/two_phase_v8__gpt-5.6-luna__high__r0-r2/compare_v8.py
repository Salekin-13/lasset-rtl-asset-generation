"""two_phase_v8 (v7 + seven prompt rules from the v7 failure analysis) against v7, on the 15 tuning modules and, once
both versions have runs there, on the 26 held-out modules. Read-only on stored files; writes compare_v8.json.

Exact scorer (names equal, each reference entry used once; findable = reference names present in the module's closed
set: 109 for the tuning modules, 187 for the held-out ones). Reported:
  - completeness per run (every module in both phases, nothing pending);
  - per run and pooled precision (correct / listed) and recall (correct / findable);
  - the readings set in prompts/two_phase_v8/README.md before the run;
  - the 16 target elements of the rules (the blind test's gains on the stored v7 replies): in how many v8 runs each is
    found, against v7;
  - element losses: found in all 3 v7 runs, in at most 1 v8 run;
  - new false positives: listed primaries of v8 that are not reference finds and that no v7 run listed;
  - a module-level sign test (per module, correct summed over the runs, v8 against v7).

Self-test (runs first): on v7 this scorer gives 92/89/86 correct of 146/158/131 listed (compare_v7.py) and equals
compare_condensed.score() on every tuning module and run.

  python compare_v8.py                 (tuning modules)
  python compare_v8.py --heldout       (held-out modules; needs v7 and v8 runs on them)
"""
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parents[2] / "src"))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402

MODEL, EFF, REPS = "gpt-5.6-luna", "high", (0, 1, 2)
V7, V8 = "two_phase_v7", "two_phase_v8"
TARGETS = ["bus:a_req", "bus:b_req", "bus:stb", "cache:cache_i.sta_hit", "cpu:alu_add", "cpu:lsu_mar",
           "cpu_cp_muldiv:ctrl.rs1_is_signed", "cpu_cp_muldiv:ctrl.rs2_is_signed", "debug_dtm:jtag_tms_i", "imem:addr",
           "sys:enable_i", "trng:data_o", "trng:fifo.avail", "trng:fifo_clr", "uart:clkgen_en_o", "wdt:reset_wdt"]
R_LOW, R_HIGH, P_LOW = 86 / 109, 92 / 109, 89 / 158  # v7's lowest and highest recall run, lowest precision run (tuning), exact


def refs(mods):
    import eval_assets as ea
    with CH.at_root():
        r = ea.load_refs()["gt"]
    out = {}
    for m in mods:
        names = {n for (_, n) in CH.closed_names(m)}
        out[m] = [n for n, _ in r[m] if n in names]
    return out


def score(v, r, m, ref):
    f = CH.run_dir(v, MODEL, r, EFF) / "assets" / f"{m}.json"
    if not f.exists():
        return None
    names = [x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]]
    listed, kth, found = Counter(names), Counter(), []
    for n in ref[m]:
        kth[n] += 1
        if listed[n] > 0:
            listed[n] -= 1
            found.append(f"{m.replace('neorv32_', '')}:{n}#{kth[n]}")
    return len(names), len(found), found, {f"{m.replace('neorv32_', '')}:{n}" for n in names}


def runs(v, mods, ref):
    out = {}
    for r in REPS:
        T = L = 0
        cs, ls, per, missing = set(), set(), {}, []
        for m in mods:
            s = score(v, r, m, ref)
            if s is None:
                missing.append(m)
                continue
            L, T = L + s[0], T + s[1]
            cs |= set(s[2])
            ls |= s[3]
            per[m] = s[1]
        out[r] = {"correct": T, "listed": L, "cset": cs, "lset": ls, "per": per, "missing": missing}
    return out


def sign_p(a, b):
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n)


def selftest(ref):
    import compare_condensed as CC
    x = runs(V7, CC.MODS, ref)
    ok = [(x[r]["correct"], x[r]["listed"]) for r in REPS] == [(92, 146), (89, 158), (86, 131)]
    ok &= all(score(V7, r, m, ref)[:3] == CC.score(V7, r, m)[:3] for r in REPS for m in CC.MODS)
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    held = "--heldout" in sys.argv
    tuning = K.gt_modules()["tuning"]
    mods = K.gt_modules()["heldout"] if held else tuning
    ref = refs(sorted(set(mods) | set(tuning)))
    ok = selftest(ref)
    print("self-test (v7 92/89/86 of 146/158/131; equal to compare_condensed.score on every tuning module and run):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    findable = sum(len(ref[m]) for m in mods)
    X = {k: runs(v, mods, ref) for k, v in (("v7", V7), ("v8", V8))}
    for k, x in X.items():
        miss = {r: y["missing"] for r, y in x.items() if y["missing"]}
        if miss:
            print(f"{k}: modules without an assets file, per run: { {r: len(v) for r, v in miss.items()} } -> not read")
            if k == "v8" or held:
                return
    rep = {"modules": "held-out" if held else "tuning", "findable per run": findable}
    for k, x in X.items():
        T, L = sum(y["correct"] for y in x.values()), sum(y["listed"] for y in x.values())
        rep[k] = {"per run (correct, listed, precision, recall)": {r: (y["correct"], y["listed"], round(y["correct"] / y["listed"], 3), round(y["correct"] / findable, 3)) for r, y in x.items()},
                  "pooled precision": f"{T}/{L} = {T / L:.3f}", "pooled recall": f"{T}/{findable * 3} = {T / (findable * 3):.3f}"}
        print(f"{k}: {rep[k]['per run (correct, listed, precision, recall)']} | pooled P {rep[k]['pooled precision']} R {rep[k]['pooled recall']}")
    v7, v8 = X["v7"], X["v8"]
    f7 = Counter(e.split("#")[0] for y in v7.values() for e in y["cset"])
    f8 = Counter(e.split("#")[0] for y in v8.values() for e in y["cset"])
    lost = sorted(e for e in f7 if f7[e] == 3 and f8[e] <= 1)
    up = sum(sum(v8[r]["per"][m] for r in REPS) > sum(v7[r]["per"][m] for r in REPS) for m in mods)
    dn = sum(sum(v8[r]["per"][m] for r in REPS) < sum(v7[r]["per"][m] for r in REPS) for m in mods)
    rep["element losses (all 3 v7 runs, at most 1 v8 run)"] = lost
    rep["module-level sign test vs v7"] = f"up {up}, down {dn}, p = {sign_p(up, dn):.2f}"
    correct_names7 = {e.split("#")[0] for y in v7.values() for e in y["cset"]}
    new_fp = sorted({e for y in v8.values() for e in y["lset"]} - {e for y in v7.values() for e in y["lset"]} - {e.split("#")[0] for y in v8.values() for e in y["cset"]})
    rep["new false positives (listed in v8, in no v7 run, not a reference find)"] = new_fp
    if not held:
        R = {r: v8[r]["correct"] / findable for r in REPS}
        Pv = {r: v8[r]["correct"] / v8[r]["listed"] for r in REPS}
        strict = [t for t in TARGETS if f7[t] <= 1]
        rec = [t for t in strict if f8[t] >= 2]
        hit7 = sum(1 for r in REPS if "cache:hit_o" in v7[r]["lset"])
        hit8 = sum(1 for r in REPS if "cache:hit_o" in v8[r]["lset"])
        rep["targets: found in how many runs (v7 -> v8)"] = {t: f"{f7[t]} -> {f8[t]}" for t in TARGETS}
        rep["READINGS (prompts/two_phase_v8/README.md)"] = {
            f"1. of the {len(strict)} targets found in at most 1 v7 run, found in 2+ v8 runs: at least half supports the rules": f"{len(rec)} of {len(strict)} -> {'supports' if 2 * len(rec) >= len(strict) else 'FALSIFIED'}",
            "2. recall below 86/109 = 0.789 (v7's lowest) in 2+ runs falsifies 'v8 does not cost recall'": f"runs {[r for r in R if R[r] < R_LOW]} -> {'FALSIFIED' if sum(R[r] < R_LOW for r in R) >= 2 else 'held'}",
            "2b. recall above 92/109 = 0.844 (v7's highest) in 2+ runs supports a gain": f"runs {[r for r in R if R[r] > R_HIGH]} -> {'yes' if sum(R[r] > R_HIGH for r in R) >= 2 else 'no'}",
            "3. precision below 89/158 = 0.563 (v7's lowest) in 2+ runs falsifies 'v8 keeps v7's precision'": f"runs {[r for r in Pv if Pv[r] < P_LOW]} -> {'FALSIFIED' if sum(Pv[r] < P_LOW for r in Pv) >= 2 else 'held'}",
            "4. B1: the child hit output listed in 2+ v8 runs, or the parent hit field found in at most 1, falsifies B1": f"hit_o listed v7 {hit7} -> v8 {hit8}; cache_i.sta_hit found v7 {f7['cache:cache_i.sta_hit']} -> v8 {f8['cache:cache_i.sta_hit']} -> {'FALSIFIED' if hit8 >= 2 or f8['cache:cache_i.sta_hit'] <= 1 else 'held'}",
            "5. element losses: any element found in all 3 v7 runs and at most 1 v8 run is a rule applied beyond its text": lost or "none",
        }
    for k in [k for k in rep if k not in ("v7", "v8")]:
        print(f"{k}: {json.dumps(rep[k], indent=1) if isinstance(rep[k], (dict, list)) else rep[k]}")
    (HERE / ("compare_v8_heldout.json" if held else "compare_v8.json")).write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
