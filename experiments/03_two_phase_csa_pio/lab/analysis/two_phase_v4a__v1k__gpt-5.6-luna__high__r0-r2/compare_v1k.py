"""Low-cost check of two_phase_v4a on inputs v1k (exact ARROWS key line) against v4 and v4a on inputs v1.
gpt-5.6-luna, high, three runs each, 15 tuning modules. Code only, no judges.

Same prompt files as v4a on v1 (system sha12 b13686bbccbf / 1c69fe88de91), so v4a-v1 vs v4a-v1k isolates the key line.
Structural numbers: each pack3.json (exact scorer, self-tested builder). Bus record ports/fields: c10_busfields (self-test).
Variation: the measures of ../two_phase_v4a__gpt-5.6-luna__high__r0-r2/variation.py (within-module permutation test).
Key-line mechanism: Phase 2 rows of ctrl.prsc in spi and twi, whose index use is only tested (spi rtl 371, twi rtl 257),
so the v1k key says it only decides the clock generator (analysis/prompt_builds/DIAGRAM_KEY_FIX.md).
Writes compare_v1k.json.

  python compare_v1k.py
"""
import json
import math
import random
import statistics as st
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
LAB = HERE.parents[1]
sys.path.insert(0, str(AN / "two_phase_v2__gpt-5.6-luna__high__r0-r2" / "p1_rules"))
sys.path.insert(0, str(AN / "two_phase_v4a__gpt-5.6-luna__high__r0-r2"))
import c10_busfields as BF  # noqa: E402
import variation as VA  # noqa: E402

RUNS = ("r0", "r1", "r2")
V = {"v4": ("two_phase_v4__gpt-5.6-luna__high__r0-r2", "two_phase_v4__v1"),
     "v4a-v1": ("two_phase_v4a__gpt-5.6-luna__high__r0-r2", "two_phase_v4a__v1"),
     "v4a-v1k": ("two_phase_v4a__v1k__gpt-5.6-luna__high__r0-r2", "two_phase_v4a__v1k")}


def sign_test(plus, minus):
    n = plus + minus
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(plus, minus) + 1)) / 2 ** n)


def reply(path):
    r = json.loads(path.read_text(encoding="utf-8"))["reply"]
    return json.loads(r) if isinstance(r, str) else r


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    BF.selftest()
    P = {v: json.loads((AN / d / "pack3.json").read_text(encoding="utf-8")) for v, (d, _) in V.items()}
    mods = list(P["v4"]["modules"])
    assert all(list(P[v]["modules"]) == mods for v in V)
    NF = P["v4"]["entries"] - P["v4"]["absent"]
    out = {"structural": {}, "pooled": {}, "variation": {}, "modules": {}}
    print(f"exact scorer, of {NF} findable reference elements")
    print("version  run listed  TP   FP   P      R      F1    busFP concepts primaryRows")
    for v in V:
        for k in RUNS:
            t = P[v]["totals"][k]
            busf = sum(1 for m in mods for x in P[v]["modules"][m]["runs"][k]["listed"]
                       if BF.is_bus(m, x["entity"], x["element"]) and not Counter(P[v]["modules"][m]["runs"][k]["tp"].values())[x["element"]])
            conc = sum(len(P[v]["modules"][m]["runs"][k]["concepts"]) for m in mods)
            p, r = t["tp"] / t["listed"], t["tp"] / NF
            out["structural"][f"{v} {k}"] = {"listed": t["listed"], "tp": t["tp"], "fp": t["fp"], "P": p, "R": r, "F1": 2 * p * r / (p + r),
                                             "bus_fp": busf, "concepts": conc}
            print(f"{v:8s} {k}  {t['listed']:5d} {t['tp']:4d} {t['fp']:4d}  {p:.3f}  {r:.3f}  {2 * p * r / (p + r):.3f}  {busf:4d}  {conc:5d}")
        L = sum(P[v]["totals"][k]["listed"] for k in RUNS)
        T = sum(P[v]["totals"][k]["tp"] for k in RUNS)
        out["pooled"][v] = {"P": T / L, "R": T / (3 * NF), "tp": T, "listed": L}
        print(f"{v:8s} pooled over 3 runs: precision {T / L:.3f} ({T}/{L}), recall {T / (3 * NF):.3f} ({T}/{3 * NF})")
    for f in ("P", "R", "F1", "tp", "bus_fp", "concepts"):
        for base in ("v4", "v4a-v1"):
            a = [out["structural"][f"{base} {k}"][f] for k in RUNS]
            b = [out["structural"][f"v4a-v1k {k}"][f] for k in RUNS]
            side = ["below" if x < min(a) else "above" if x > max(a) else "inside" for x in b]
            fmt = (lambda x: f"{x:.3f}") if isinstance(a[0], float) else str
            print(f"  {f:8s} vs {base:7s} range {fmt(min(a))}-{fmt(max(a))}: v1k {', '.join(fmt(x) for x in b)} -> {', '.join(side)}")
    print("\nper module correct finds r0/r1/r2 (findable): v4 | v4a-v1 | v4a-v1k ; false positives the same way")
    for m in mods:
        s = m.replace("neorv32_", "")
        tp = {v: [len(P[v]["modules"][m]["runs"][k]["tp"]) for k in RUNS] for v in V}
        fp = {v: [len(P[v]["modules"][m]["runs"][k]["fp"]) for k in RUNS] for v in V}
        out["modules"][s] = {"tp": tp, "fp": fp}
        nref = sum(1 for e in P["v4"]["modules"][m]["reference entries"] if not e["absent"])
        print(f"  {s:14s} ({nref:2d}) TP {' | '.join('/'.join(map(str, tp[v])) for v in V):28s} FP {' | '.join('/'.join(map(str, fp[v])) for v in V)}")
    # element level
    cnt, names = {v: Counter() for v in V}, {}
    for v in V:
        for m in mods:
            for e in P[v]["modules"][m]["reference entries"]:
                if not e["absent"]:
                    names[e["entry"]] = f"{m.replace('neorv32_', '')}:{e['name']}"
                    cnt[v][e["entry"]] += sum(e["entry"] in P[v]["modules"][m]["runs"][k]["tp"] for k in RUNS)
    ids = sorted(names)
    out["elements"] = {}
    for base in ("v4a-v1", "v4"):
        plus = [i for i in ids if cnt["v4a-v1k"][i] > cnt[base][i]]
        minus = [i for i in ids if cnt["v4a-v1k"][i] < cnt[base][i]]
        p = sign_test(len(plus), len(minus))
        print(f"\nv1k vs {base}: found in more runs {len(plus)}, fewer {len(minus)}, same {len(ids) - len(plus) - len(minus)}; sign test p = {p:.3f}")
        for i in plus + minus:
            print(f"   {names[i]:30s} v4 {cnt['v4'][i]}/3  v4a-v1 {cnt['v4a-v1'][i]}/3  v4a-v1k {cnt['v4a-v1k'][i]}/3")
        out["elements"][base] = {"more": [names[i] for i in plus], "fewer": [names[i] for i in minus], "p": p}
    for v in V:
        d = {n: sum(cnt[v][i] == n for i in ids) for n in (3, 2, 1, 0)}
        out["elements"][f"dist {v}"] = d
        print(f"  {v}: found in 3/2/1/0 runs: {d[3]}/{d[2]}/{d[1]}/{d[0]}")
    # variation (same measures as variation.py)
    rng = random.Random(20261012)
    print("\nvariation: range of run totals, sum of within-module variances, alignment, unstable elements, permutation p")
    for v in V:
        mod_tp = [[len(P[v]["modules"][m]["runs"][k]["tp"]) for k in RUNS] for m in mods]
        tot = [sum(x[i] for x in mod_tp) for i in range(3)]
        mv = sum(st.pvariance(x) for x in mod_tp)
        unstable = sum(1 for i in ids if cnt[v][i] in (1, 2))
        pp = VA.perm_p(mod_tp, max(tot) - min(tot), rng)
        out["variation"][v] = {"range": max(tot) - min(tot), "module_var": mv, "alignment": st.pvariance(tot) - mv, "unstable": unstable, "perm_p": pp}
        print(f"  {v:8s} totals {tot} range {max(tot) - min(tot)}  module var {mv:.2f}  alignment {st.pvariance(tot) - mv:+.2f}  unstable {unstable}  perm p {pp:.3f}")
    # key-line mechanism: ctrl.prsc rows in spi and twi
    print("\nctrl.prsc Phase 2 rows (spi, twi): label, concept, reason")
    out["prsc"] = {}
    for v, (_, rd) in V.items():
        for s in ("spi", "twi"):
            for k in RUNS:
                f = LAB / "runs" / rd / "gpt-5.6-luna__high" / k / "phase2" / f"neorv32_{s}.json"
                rows = [x for x in reply(f).get("structural assets", []) if x.get("element") == "ctrl.prsc"]
                out["prsc"][f"{v} {s} {k}"] = [[x.get("label"), x.get("concept id"), x.get("reason")] for x in rows]
                for x in rows:
                    print(f"  {v:8s} {s} {k} {x.get('label'):9s} {x.get('concept id'):4s} {x.get('reason')}")
    (HERE / "compare_v1k.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nwrote compare_v1k.json")


if __name__ == "__main__":
    main()
