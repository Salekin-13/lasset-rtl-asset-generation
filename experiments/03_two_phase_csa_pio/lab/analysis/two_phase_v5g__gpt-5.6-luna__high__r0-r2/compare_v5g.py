"""two_phase_v5g (v5f + Phase 1/Phase 2 consistency fix in phase2.md) vs two_phase_v5f, gpt-5.6-luna, high, inputs v1.
v5g: r0-r2 (full runs). v5f: r0-r2 and r3-r5 (six full runs; r3-r5 were run as the control, with new Phase 1 calls).
Both versions share the Phase 1 prompt (system sha f05279744fdc), so Phase 1 differences between them are chance.

Exact scorer (names equal, each reference entry used once; absent names excluded). Only modules whose assets file
exists in EVERY compared run are scored, and the module set is printed, so an incomplete run never looks like a loss.
Writes compare_v5g.json. Self-test: v5f r0-r2 on all 15 modules reproduce compare_v5f.json (91/85/92 correct).

  python compare_v5g.py
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402

MODEL, EFF = "gpt-5.6-luna", "high"
RUNS = {"v5g": ("two_phase_v5g", (0, 1, 2)), "v5f": ("two_phase_v5f", (0, 1, 2, 3, 4, 5))}


def refs():
    import eval_assets as ea
    with CH.at_root():
        r = ea.load_refs()["gt"]
    out = {}
    for m in CH.tuning_modules():
        names = {n for (_, n) in CH.closed_names(m)}
        out[m] = [n for n, _ in r[m] if n in names]
    return out


REF = refs()


def score(version, rep, mods):
    L = T = 0
    found = Counter()
    for m in mods:
        a = json.loads((CH.run_dir(version, MODEL, rep, EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))
        listed = Counter(x["Asset RTL"] for x in a["Assets"])
        L += sum(listed.values())
        kth = Counter()
        for n in REF[m]:
            kth[n] += 1
            if listed[n] > 0:
                listed[n] -= 1
                T += 1
                found[f"{m.replace('neorv32_', '')}:{n}#{kth[n]}"] += 1
    F = sum(len(REF[m]) for m in mods)
    return {"listed": L, "correct": T, "fp": L - T, "findable": F, "precision": round(T / L, 3) if L else None,
            "recall": round(T / F, 3) if F else None}, found


def sign_test(a, b):
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mods_all = CH.tuning_modules()
    s, _ = score("two_phase_v5f", 0, mods_all)
    s1, _ = score("two_phase_v5f", 1, mods_all)
    s2, _ = score("two_phase_v5f", 2, mods_all)
    ok = (s["correct"], s1["correct"], s2["correct"]) == (91, 85, 92)
    print("self-test (v5f r0-r2 correct 91/85/92):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    have = {(k, r): {m for m in mods_all if (CH.run_dir(v, MODEL, r, EFF) / "assets" / f"{m}.json").exists()}
            for k, (v, reps) in RUNS.items() for r in reps}
    common = sorted(set.intersection(*have.values()))
    missing = {f"{k} r{r}": sorted(m.replace("neorv32_", "") for m in set(mods_all) - h) for (k, r), h in have.items() if set(mods_all) - h}
    print(f"modules complete in every run: {len(common)} of {len(mods_all)}; missing: {missing or 'none'}")
    res = {"common modules": common, "missing": missing, "runs": {}}
    found = {}
    for k, (v, reps) in RUNS.items():
        found[k] = Counter()
        for r in reps:
            sc, f = score(v, r, common)
            res["runs"][f"{k} r{r}"] = sc
            found[k] += f
            print(f"  {k} r{r}: listed {sc['listed']} correct {sc['correct']} FP {sc['fp']}  precision {sc['precision']}  "
                  f"recall {sc['recall']} (of {sc['findable']})")
    for k, (v, reps) in RUNS.items():
        L = sum(res["runs"][f"{k} r{r}"]["listed"] for r in reps)
        T = sum(res["runs"][f"{k} r{r}"]["correct"] for r in reps)
        F = sum(res["runs"][f"{k} r{r}"]["findable"] for r in reps)
        res[f"pooled {k}"] = {"precision": round(T / L, 3), "recall": round(T / F, 3), "correct": T, "listed": L, "findable": F}
        print(f"  pooled {k}: precision {T}/{L} = {T / L:.3f}; recall {T}/{F} = {T / F:.3f}")
    # element level: share of runs found, v5g (3 runs) vs v5f (6 runs)
    els = sorted(set(found["v5g"]) | set(found["v5f"]) | {f"{m.replace('neorv32_', '')}:{n}#{i}" for m in common
                                                          for n, i in Counter(REF[m]).items() for i in range(1, i + 1)})
    up = [e for e in els if found["v5g"][e] / 3 > found["v5f"][e] / 6 + 1e-9]
    down = [e for e in els if found["v5g"][e] / 3 < found["v5f"][e] / 6 - 1e-9]
    print(f"  elements found in a larger share of runs in v5g: {len(up)}; smaller: {len(down)}; sign test p = {sign_test(len(up), len(down)):.2f}")
    print("    larger :", ", ".join(f"{e.split('#')[0]} {found['v5f'][e]}/6->{found['v5g'][e]}/3" for e in up))
    print("    smaller:", ", ".join(f"{e.split('#')[0]} {found['v5f'][e]}/6->{found['v5g'][e]}/3" for e in down))
    res["element shares"] = {e: {"v5f of 6": found["v5f"][e], "v5g of 3": found["v5g"][e]} for e in els}
    (HERE / "compare_v5g.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
