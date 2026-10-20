"""Run-to-run variation of every Luna two-phase version (v1, v2, v2a, v3, v4, v4a; three runs each, 15 tuning modules).

Question (user, 2026-10-12): v4a's runs spread more than v4's; is that conciseness or specificity?

Each module is its own pair of API calls, so a "run" is only a label on 15 independent module results. The spread of the
run totals is therefore the sum of per-module noise plus how the per-module dips happen to line up under one label.
Measured per version, all from pack3.json (exact scorer, self-tested builder) and the stored replies' usage fields:
  totals      correct finds per run, their range and SD
  module var  sum over modules of the variance of that module's correct finds across the 3 runs (noise inside modules)
  alignment   variance of the run totals minus the summed module variances (= 2 x the covariances: dips lining up)
  unstable    reference elements found in 1 or 2 of the 3 runs
  perm p      within-module permutation test: run labels shuffled independently inside each module (200,000 draws);
              p = share of draws whose run-total range is at least the observed one
  jaccard     mean over modules and run pairs of the Jaccard overlap of the listed primary elements
  tokens      Phase 1 and Phase 2 reasoning tokens per run (sum over modules)
Self-test: per-module correct finds must add up to pack3.json's totals; the permutation code must give p = 1 for a
version whose modules never vary, and the observed range must be reachable by its own draw.

  python variation.py
"""
import json
import random
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
LAB = HERE.parents[1]
VERS = ["v1", "v2", "v2a", "v3", "v4", "v4a"]
RUNS = ("r0", "r1", "r2")
NDRAW = 200_000


def pvar(xs):
    return st.pvariance(xs)


def perm_p(mod_tp, observed_range, rng):
    """mod_tp: list of [tp_r0, tp_r1, tp_r2] per module. Shuffle each module's triple independently."""
    hits = 0
    for _ in range(NDRAW):
        tot = [0, 0, 0]
        for t in mod_tp:
            a = t[:]
            rng.shuffle(a)
            tot[0] += a[0]
            tot[1] += a[1]
            tot[2] += a[2]
        if max(tot) - min(tot) >= observed_range:
            hits += 1
    return hits / NDRAW


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    rng = random.Random(20261012)
    # self-test of the permutation code
    assert perm_p([[3, 3, 3], [5, 5, 5]], 0, rng) == 1.0
    assert perm_p([[0, 0, 1]] * 4, 4, rng) > 0, "a range of 4 is reachable"
    out = {}
    print("version | correct finds r0/r1/r2 | range | SD | sum of module variances | alignment | unstable elements | perm p | Jaccard | reasoning tokens P1 / P2 per run (thousands)")
    for v in VERS:
        P = json.loads((AN / f"two_phase_{v}__gpt-5.6-luna__high__r0-r2" / "pack3.json").read_text(encoding="utf-8"))
        mods = list(P["modules"])
        mod_tp = [[len(P["modules"][m]["runs"][k]["tp"]) for k in RUNS] for m in mods]
        tot = [sum(x[i] for x in mod_tp) for i in range(3)]
        assert tot == [P["totals"][k]["tp"] for k in RUNS], (v, tot)          # self-test against the pack
        rng_obs = max(tot) - min(tot)
        mv = sum(pvar(x) for x in mod_tp)
        align = pvar(tot) - mv
        unstable = 0
        for m in mods:
            for e in P["modules"][m]["reference entries"]:
                if e["absent"]:
                    continue
                n = sum(e["entry"] in P["modules"][m]["runs"][k]["tp"] for k in RUNS)
                unstable += n in (1, 2)
        jac = []
        for m in mods:
            sets = [{(x["entity"], x["element"]) for x in P["modules"][m]["runs"][k]["listed"]} for k in RUNS]
            for i, j in ((0, 1), (0, 2), (1, 2)):
                u = sets[i] | sets[j]
                if u:
                    jac.append(len(sets[i] & sets[j]) / len(u))
        toks = {}
        for k in RUNS:
            rd = LAB / "runs" / f"two_phase_{v}__v1" / "gpt-5.6-luna__high" / k
            for ph in (1, 2):
                toks[(k, ph)] = sum(json.loads(f.read_text(encoding="utf-8"))["usage"].get("reasoning", 0)
                                    for f in (rd / f"phase{ph}").glob("neorv32_*.json")) / 1000
        p = perm_p(mod_tp, rng_obs, rng)
        out[v] = {"tp": tot, "range": rng_obs, "sd": st.pstdev(tot), "module_var": mv, "alignment": align, "unstable": unstable,
                  "perm_p": p, "jaccard": st.mean(jac), "mod_tp": dict(zip([m.replace("neorv32_", "") for m in mods], mod_tp)),
                  "reasoning_k": {f"{k} P{ph}": round(toks[(k, ph)], 1) for (k, ph) in toks}}
        print(f"{v:4s} | {'/'.join(map(str, tot)):9s} | {rng_obs:2d} | {st.pstdev(tot):.2f} | {mv:5.2f} | {align:+6.2f} | {unstable:2d} | "
              f"{p:.3f} | {st.mean(jac):.3f} | " + "  ".join(f"{toks[(k, 1)]:.0f}/{toks[(k, 2)]:.0f}" for k in RUNS))
    # where v4a r1 lost: modules where r1 is the lowest run, v4a and v4
    print("\nmodules where one run is strictly lowest (that run's label):")
    for v in ("v4", "v4a"):
        low = {}
        for s, t in out[v]["mod_tp"].items():
            mn = min(t)
            if t.count(mn) == 1:
                low[s] = RUNS[t.index(mn)]
        print(f"  {v}: " + ", ".join(f"{s}={k}" for s, k in low.items()) + f"  -> per run {[list(low.values()).count(k) for k in RUNS]}")
        out[v]["lowest_run_by_module"] = low
    (HERE / "variation.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nwrote variation.json")


if __name__ == "__main__":
    main()
