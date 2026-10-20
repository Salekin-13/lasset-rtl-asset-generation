"""two_phase_v6 (v5g + 24 paired Phase 1 / Phase 2 rules) vs two_phase_v5g (3 runs) and two_phase_v5f (6 runs),
gpt-5.6-luna, high, inputs v1. All full runs. Read-only on stored files; writes compare_v6.json and prints a report.

Exact scorer (names equal, each reference entry used once; the 2 absent names excluded; 109 findable per run).
Includes: per-run and pooled precision/recall; per module correct/listed; element shares (v6 of 3 vs v5g of 3 vs v5f
of 6); the falsifiers set in prompts/two_phase_v6/README.md; format problems on the replies as written (including the
nesting slip seen in v5g r0 bus); Phase 1 concept counts; cost from the stored usage.
Self-tests: v5g r0-r2 correct 82/89/95 and v5f r0-r2 correct 91/85/92 (compare_v5g.json / compare_v5f.json).

  python compare_v6.py
"""
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB.parents[2] / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import cost_estimate as CE  # noqa: E402

MODEL, EFF = "gpt-5.6-luna", "high"
VERS = {"v6": ("two_phase_v6", (0, 1, 2)), "v5g": ("two_phase_v5g", (0, 1, 2)), "v5f": ("two_phase_v5f", (0, 1, 2, 3, 4, 5))}
MODS = CH.tuning_modules()


def refs():
    import eval_assets as ea
    with CH.at_root():
        r = ea.load_refs()["gt"]
    out = {}
    for m in MODS:
        names = {n for (_, n) in CH.closed_names(m)}
        out[m] = [n for n, _ in r[m] if n in names]
    return out


REF = refs()


def score(version, rep, m):
    a = json.loads((CH.run_dir(version, MODEL, rep, EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))
    listed = Counter(x["Asset RTL"] for x in a["Assets"])
    L, T, found = sum(listed.values()), 0, []
    kth = Counter()
    for n in REF[m]:
        kth[n] += 1
        if listed[n] > 0:
            listed[n] -= 1
            T += 1
            found.append(f"{m.replace('neorv32_', '')}:{n}#{kth[n]}")
    return L, T, found


def sign_test(a, b):
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    runs, found, per_mod = {}, {k: Counter() for k in VERS}, defaultdict(dict)
    for k, (v, reps) in VERS.items():
        for r in reps:
            L = T = 0
            for m in MODS:
                l, t, f = score(v, r, m)
                L += l
                T += t
                found[k].update(f)
                per_mod[m][f"{k} r{r}"] = (t, l)
            runs[f"{k} r{r}"] = {"listed": L, "correct": T, "fp": L - T, "precision": round(T / L, 3), "recall": round(T / 109, 3),
                                 "f1": round(2 * (T / L) * (T / 109) / ((T / L) + (T / 109)), 3)}
    ok = [runs[f"v5g r{r}"]["correct"] for r in (0, 1, 2)] == [82, 89, 95] and [runs[f"v5f r{r}"]["correct"] for r in (0, 1, 2)] == [91, 85, 92]
    print("self-test (v5g 82/89/95, v5f r0-r2 91/85/92):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    print("\nPER RUN (exact; recall of 109)")
    for key, s in runs.items():
        print(f"  {key:7s} listed {s['listed']:3d} correct {s['correct']:3d} FP {s['fp']:3d}  precision {s['precision']:.3f}  recall {s['recall']:.3f}  F1 {s['f1']:.3f}")
    pooled = {}
    for k, (v, reps) in VERS.items():
        L = sum(runs[f"{k} r{r}"]["listed"] for r in reps)
        T = sum(runs[f"{k} r{r}"]["correct"] for r in reps)
        pooled[k] = {"precision": round(T / L, 3), "recall": round(T / (109 * len(reps)), 3), "correct": T, "listed": L, "findable": 109 * len(reps)}
        print(f"  pooled {k:4s}: precision {T}/{L} = {T / L:.3f}; recall {T}/{109 * len(reps)} = {T / (109 * len(reps)):.3f}")
    # falsifiers from the v6 README
    p6 = [runs[f"v6 r{r}"]["precision"] for r in (0, 1, 2)]
    r6 = [runs[f"v6 r{r}"]["recall"] for r in (0, 1, 2)]
    allel = sorted(set(found["v6"]) | set(found["v5g"]) | set(found["v5f"]))
    lost = [e for e in allel if found["v5f"][e] >= 5 and found["v5g"][e] >= 2 and found["v6"][e] <= 1]
    print("\nFALSIFIERS (set before the run, prompts/two_phase_v6/README.md)")
    print(f"  1. precision above 0.500 in at least 2 of 3 v6 runs: {sum(p > 0.5 for p in p6)} of 3 ({p6}) -> {'held' if sum(p > 0.5 for p in p6) >= 2 else 'FALSIFIED'}")
    print(f"  2. recall below 0.780 in 2 or more v6 runs: {sum(r < 0.78 for r in r6)} of 3 ({r6}) -> {'FALSIFIED' if sum(r < 0.78 for r in r6) >= 2 else 'held'}")
    print(f"  3. elements found in >=5/6 v5f and >=2/3 v5g runs but <=1 v6 run: {len(lost)} {[e.split('#')[0] for e in lost]}")
    # element shares
    print("\nELEMENT SHARES (v6 of 3 vs v5g of 3 / v5f of 6)")
    for base in ("v5g", "v5f"):
        nb = 3 if base == "v5g" else 6
        up = [e for e in allel if found["v6"][e] / 3 > found[base][e] / nb + 1e-9]
        down = [e for e in allel if found["v6"][e] / 3 < found[base][e] / nb - 1e-9]
        print(f"  vs {base}: found in a larger share {len(up)}, smaller {len(down)}; sign test p = {sign_test(len(up), len(down)):.2f}")
        if base == "v5g":
            print("    larger :", ", ".join(f"{e.split('#')[0]} {found['v5g'][e]}->{found['v6'][e]}" for e in up))
            print("    smaller:", ", ".join(f"{e.split('#')[0]} {found['v5g'][e]}->{found['v6'][e]}" for e in down))
    # per module
    print("\nPER MODULE correct/listed (ref = findable)")
    keys = [f"v6 r{r}" for r in (0, 1, 2)] + [f"v5g r{r}" for r in (0, 1, 2)]
    print(f"  {'module':14s} ref  " + "  ".join(k.ljust(9) for k in keys) + "  v5f mean correct/listed")
    for m in MODS:
        f6 = [per_mod[m][f'v5f r{r}'] for r in range(6)]
        print(f"  {m.replace('neorv32_', ''):14s} {len(REF[m]):3d}  " + "  ".join(f"{per_mod[m][k][0]}/{per_mod[m][k][1]}".ljust(9) for k in keys)
              + f"  {sum(x[0] for x in f6) / 6:.1f}/{sum(x[1] for x in f6) / 6:.1f}")
    # format problems on the replies as written, Phase 1 concepts, nesting slip, cost
    print("\nFORMAT, CONCEPTS AND COST (v6 r0 / r1 / r2)")
    P = CE.PRICES[MODEL]
    for r in (0, 1, 2):
        c = Counter()
        usd = 0.0
        for m in MODS:
            run = CH.run_dir("two_phase_v6", MODEL, r, EFF)
            rec1 = json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
            rec2 = json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
            p1, p2 = K.parse_json(rec1["raw"]), K.parse_json(rec2["raw"])
            ids = [x.get("Concept ID") for x in p1.get("Conceptual Assets", []) if isinstance(x, dict)]
            c["concepts"] += len(ids)
            c["not kept"] += len(p1.get("Not Kept", []) or [])
            _, a = CH.from_format_phase1(p1, rec1["raw"])
            _, b = CH.from_format_phase2(p2, rec2["raw"], ids)
            c["format/consistency problems"] += len(a) + len(b)
            c["replies with problems"] += bool(a) + bool(b)
            for w in p2.get("Concept Walks", []) or []:
                if not isinstance(w, dict):
                    continue
                c["walks"] += 1
                inner = sum(len(p.get("Assets") or []) for p in (w.get("Points") or []) if isinstance(p, dict) and isinstance(p.get("Assets"), list))
                c["asset rows nested inside points (slip)"] += inner
                ass = [x for x in (w.get("Assets") or []) if isinstance(x, dict)]
                c["asset rows"] += len(ass)
                c["asset rows without Asset RTL"] += sum(1 for x in ass if not x.get("Asset RTL"))
                c["walks with no primary"] += not any(x.get("Label") == "primary" for x in ass)
            for rec in (rec1, rec2):
                u = rec["usage"]
                cc = u.get("cached") or 0
                usd += ((u["in"] - cc) * P["in"] + cc * P["cached"] + u["out"] * P["out"]) / 1e6
        c["usd"] = round(usd, 2)
        print(f"  r{r}: " + ", ".join(f"{k} {v}" for k, v in c.items()))
    out = {"runs": runs, "pooled": pooled, "lost": lost, "found": {k: dict(v) for k, v in found.items()},
           "per_module": {m: {k: list(v) for k, v in d.items()} for m, d in per_mod.items()}}
    (HERE / "compare_v6.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
