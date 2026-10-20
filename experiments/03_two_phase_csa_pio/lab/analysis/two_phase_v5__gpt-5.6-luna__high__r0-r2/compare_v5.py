"""two_phase_v5 vs v4a (and v4), gpt-5.6-luna, high, three runs each, inputs v1, exact scorer (109 findable).

Reads each version's pack3.json (self-tested builder). Applies the falsification tests that prompts/two_phase_v5/README.md
set before the run, element-level changes (sign test), the recovery targets (K1, K2), bus-record false positives
(c10_busfields, self-test), run-to-run variation (variation.py's permutation test), new false positives (in v5, never
in v4a), and per-rule compliance: for every rule, the v4a false-positive elements the blind judges agreed it would remove
(rule_effects.py, both judges), and how many of them are still listed as primary in v5. Writes compare_v5.json.

  python compare_v5.py
"""
import json
import math
import random
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
A4A = AN / "two_phase_v4a__gpt-5.6-luna__high__r0-r2"
sys.path.insert(0, str(AN / "two_phase_v2__gpt-5.6-luna__high__r0-r2" / "p1_rules"))
sys.path.insert(0, str(A4A))
import c10_busfields as BF  # noqa: E402
import rule_effects as RE  # noqa: E402
import variation as VA  # noqa: E402

RUNS = ("r0", "r1", "r2")
V = {"v4": "two_phase_v4__gpt-5.6-luna__high__r0-r2", "v4a": "two_phase_v4a__gpt-5.6-luna__high__r0-r2",
     "v5": "two_phase_v5__gpt-5.6-luna__high__r0-r2"}


def sign_test(a, b):
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    BF.selftest()
    P = {v: json.loads((AN / d / "pack3.json").read_text(encoding="utf-8")) for v, d in V.items()}
    mods = list(P["v4a"]["modules"])
    NF = P["v4a"]["entries"] - P["v4a"]["absent"]
    out = {"structural": {}}
    print(f"exact scorer, {NF} findable")
    for v in V:
        for k in RUNS:
            t = P[v]["totals"][k]
            p, r = t["tp"] / t["listed"], t["tp"] / NF
            busf = sum(1 for m in mods for x in P[v]["modules"][m]["runs"][k]["fp"] if BF.is_bus(m, x["entity"], x["element"]))
            conc = sum(len(P[v]["modules"][m]["runs"][k]["concepts"]) for m in mods)
            out["structural"][f"{v} {k}"] = {"listed": t["listed"], "tp": t["tp"], "fp": t["fp"], "P": p, "R": r, "F1": 2 * p * r / (p + r), "bus_fp": busf, "concepts": conc}
            print(f"  {v:4s} {k} listed {t['listed']:4d} TP {t['tp']:3d} FP {t['fp']:4d}  P {p:.3f} R {r:.3f} F1 {2 * p * r / (p + r):.3f}  busFP {busf:3d} concepts {conc}")
        L = sum(P[v]["totals"][k]["listed"] for k in RUNS)
        T = sum(P[v]["totals"][k]["tp"] for k in RUNS)
        out["structural"][f"{v} pooled"] = {"P": T / L, "R": T / (3 * NF)}
        print(f"  {v:4s} pooled P {T / L:.3f} ({T}/{L})  R {T / (3 * NF):.3f} ({T}/{3 * NF})")
    S = out["structural"]
    pr = [S[f"v4a {k}"]["P"] for k in RUNS]
    rr = [S[f"v4a {k}"]["R"] for k in RUNS]
    above = sum(S[f"v5 {k}"]["P"] > max(pr) for k in RUNS)
    below_r = [k for k in RUNS if S[f"v5 {k}"]["R"] < min(rr)]
    # element level
    cnt, names, home = {v: Counter() for v in V}, {}, {}
    for v in V:
        for m in mods:
            for e in P[v]["modules"][m]["reference entries"]:
                if not e["absent"]:
                    names[e["entry"]] = f"{m.replace('neorv32_', '')}:{e['name']}"
                    home[e["entry"]] = e["home concept"]
                    cnt[v][e["entry"]] += sum(e["entry"] in P[v]["modules"][m]["runs"][k]["tp"] for k in RUNS)
    ids = sorted(names)
    lost_all3 = [names[i] for i in ids if cnt["v4a"][i] == 3 and cnt["v5"][i] < 2]
    print("\nREADME falsification tests (set before the run):")
    print(f"  precision above v4a's range ({min(pr):.3f}-{max(pr):.3f}) in {above} of 3 runs -> {'PASS' if above >= 2 else 'FAIL'} (needs 2)")
    print(f"  recall below v4a's range ({min(rr):.3f}-{max(rr):.3f}) in runs {below_r or 'none'} -> {'FAIL' if below_r else 'PASS'}")
    print(f"  elements found in all 3 v4a runs but in fewer than 2 v5 runs: {len(lost_all3)} -> {'FAIL' if lost_all3 else 'PASS'} {lost_all3}")
    out["tests"] = {"precision_above_runs": above, "recall_below_runs": below_r, "lost_all3": lost_all3}
    plus = [i for i in ids if cnt["v5"][i] > cnt["v4a"][i]]
    minus = [i for i in ids if cnt["v5"][i] < cnt["v4a"][i]]
    print(f"\nv5 vs v4a: found in more runs {len(plus)}, fewer {len(minus)} (sign test p = {sign_test(len(plus), len(minus)):.3f})")
    for i in plus + minus:
        print(f"   {names[i]:28s} ({home[i]})  v4 {cnt['v4'][i]}/3  v4a {cnt['v4a'][i]}/3  v5 {cnt['v5'][i]}/3")
    dist = {v: {n: sum(cnt[v][i] == n for i in ids) for n in (3, 2, 1, 0)} for v in V}
    print("  found in 3/2/1/0 runs:", {v: "/".join(str(dist[v][n]) for n in (3, 2, 1, 0)) for v in V})
    out["elements"] = {"more": [[names[i], cnt["v4a"][i], cnt["v5"][i]] for i in plus], "fewer": [[names[i], cnt["v4a"][i], cnt["v5"][i]] for i in minus],
                       "p": sign_test(len(plus), len(minus)), "dist": dist}
    print("\nrecovery targets (runs found, v4a -> v5):")
    for t in ("cpu:csr_rdata", "trng:valid_o", "cpu:lsu_mar"):
        i = next(i for i in ids if names[i] == t)
        print(f"   {t:16s} {cnt['v4a'][i]}/3 -> {cnt['v5'][i]}/3")
    # variation
    rng = random.Random(20261012)
    out["variation"] = {}
    for v in V:
        mod_tp = [[len(P[v]["modules"][m]["runs"][k]["tp"]) for k in RUNS] for m in mods]
        tot = [sum(x[i] for x in mod_tp) for i in range(3)]
        mv = sum(st.pvariance(x) for x in mod_tp)
        unstable = sum(1 for i in ids if cnt[v][i] in (1, 2))
        pp = VA.perm_p(mod_tp, max(tot) - min(tot), rng)
        out["variation"][v] = {"tot": tot, "module_var": mv, "unstable": unstable, "perm_p": pp}
        print(f"  variation {v}: totals {tot}, module var {mv:.2f}, unstable {unstable}, perm p {pp:.3f}")
    # false positives: union and new ones
    fpu = {v: defaultdict(int) for v in V}
    for v in V:
        for m in mods:
            for k in RUNS:
                for x in P[v]["modules"][m]["runs"][k]["fp"]:
                    fpu[v][(m.replace("neorv32_", ""), x["element"])] += 1
    new = sorted((k, n) for k, n in fpu["v5"].items() if k not in fpu["v4a"])
    gone = sorted(k for k in fpu["v4a"] if k not in fpu["v5"])
    print(f"\nfalse-positive elements (union over runs): v4a {len(fpu['v4a'])}, v5 {len(fpu['v5'])}; gone in v5 {len(gone)}; new in v5 {len(new)} "
          f"(listings {sum(n for _, n in new)})")
    bym = Counter(k[0] for k, _ in new)
    print("  new by module:", dict(bym.most_common()))
    for (m, e), n in new:
        print(f"   new FP {m}:{e} in {n} run(s)")
    out["fp_new"] = [[m, e, n] for (m, e), n in new]
    out["fp_gone"] = [list(k) for k in gone]
    # per-rule compliance
    key = json.loads((A4A / "boundary_key.json").read_text(encoding="utf-8"))
    W = json.loads((A4A / "rules_workflow_result.json").read_text(encoding="utf-8")); W = W.get("result", W)
    U = json.loads((A4A / "u_workflow_result.json").read_text(encoding="utf-8")); U = U.get("result", U)
    rounds = {h["round"]: h["judged"] for h in U["history"]}
    pairs = {r: W["judged"] for r in ("R1", "R3", "R4", "R5", "R2b", "R7b")}
    pairs.update({f["id"]: rounds[f["round"]] for f in U["final"] if f["status"] != "dropped"})
    print("\nper rule: v4a false-positive elements the judges agreed it removes, and how many are still primary in v5 (any run)")
    out["compliance"] = {}
    for rid, judged in pairs.items():
        eff = RE.effects_of(judged, rid, "both")
        gone_e, status = RE.apply(key, eff)
        target = sorted({(m, e) for (m, k, e) in gone_e if status[(m, k, e)] == "fp"})
        still = [t for t in target if fpu["v5"].get(t)]
        out["compliance"][rid] = {"targets": [list(t) for t in target], "still": [list(t) for t in still]}
        rate = f"{len(target) - len(still)}/{len(target)} gone" if target else "no agreed target"
        print(f"  {rid:5s} {rate:16s} still listed: {', '.join(f'{m}:{e}' for m, e in still)[:200]}")
    (HERE / "compare_v5.json").write_text(json.dumps(out, indent=1, default=list), encoding="utf-8")
    print("\nwrote compare_v5.json")


if __name__ == "__main__":
    main()
