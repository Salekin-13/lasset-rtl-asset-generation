"""Step 1c: precision and recall per run and pooled (exact matching) for v7, v6d, v6 and v5f, plus permutation tests.

Scores come from compare_v7.runs() (the compare_condensed scorer). compare_v7.py itself is not run: its main() would
overwrite compare_v7.json, which belongs to another session.

Self-tests, before anything is written:
  - compare_v7's own self-test figures: v6 correct 86/83/86 and v5f 91/85/92/94/91/88;
  - compare_condensed.selftest(): the scorer equals compare_v6.score() on every v6 run and module, v6 against itself is
    clean, and simulated runs read right;
  - the permutation code: identical groups give p = 1; a fully separated 3-vs-3 split gives the smallest p, 1/20.

Permutation tests (adapted from analysis/two_phase_v4a__gpt-5.6-luna__high__r0-r2/variation.py):
  - run level, exact: every way to split the pooled runs of v7 and a base version into groups of their sizes;
    statistic = mean per run (v7) - mean per run (base); p one-sided in the direction observed (as in V6_RESULTS.md);
  - module level, stratified: inside each module, the per-run results (correct, listed) of both versions are shuffled
    across the version labels (100,000 draws, fixed seed); statistic = pooled v7 minus pooled base (recall: correct per
    run; precision: correct / listed); p one-sided in the direction observed.
  - within v7 (variation.py's question): is the spread of v7's run totals larger than module noise alone gives?

Writes scores.json.   python rescore.py
"""
import itertools
import json
import random
import statistics as st
import sys

import common_fa as F

BASES = {"v6d": ("two_phase_v6d", (0, 1, 2)), "v6": ("two_phase_v6", (0, 1, 2)), "v5f": ("two_phase_v5f", (0, 1, 2, 3, 4, 5))}
NDRAW = 100_000


def exact_p(a, b):
    """a, b: lists of per-run values. One-sided p in the direction of the observed mean difference; also the number of
    splits."""
    obs = st.mean(a) - st.mean(b)
    pool = a + b
    n, k = len(pool), len(a)
    hits = tot = 0
    for idx in itertools.combinations(range(n), k):
        x = [pool[i] for i in idx]
        y = [pool[i] for i in range(n) if i not in idx]
        d = st.mean(x) - st.mean(y)
        tot += 1
        if (obs >= 0 and d >= obs - 1e-12) or (obs < 0 and d <= obs + 1e-12):
            hits += 1
    return obs, hits / tot, tot


def strat_p(per_mod_a, per_mod_b, metric, rng):
    """per_mod_x: {module: [(correct, listed) per run]}. Shuffle within module. metric: 'recall' or 'precision'."""
    mods = list(per_mod_a)
    ka, kb = len(next(iter(per_mod_a.values()))), len(next(iter(per_mod_b.values())))

    def stat(A, B):
        if metric == "recall":
            return sum(c for m in mods for c, _ in A[m]) / ka - sum(c for m in mods for c, _ in B[m]) / kb
        ca, la = sum(c for m in mods for c, _ in A[m]), sum(l for m in mods for _, l in A[m])
        cb, lb = sum(c for m in mods for c, _ in B[m]), sum(l for m in mods for _, l in B[m])
        return ca / la - cb / lb

    obs = stat(per_mod_a, per_mod_b)
    hits = 0
    for _ in range(NDRAW):
        A, B = {}, {}
        for m in mods:
            pool = per_mod_a[m] + per_mod_b[m]
            rng.shuffle(pool)
            A[m], B[m] = pool[:ka], pool[ka:]
        d = stat(A, B)
        if (obs >= 0 and d >= obs - 1e-12) or (obs < 0 and d <= obs + 1e-12):
            hits += 1
    return obs, hits / NDRAW


def within_p(mod_tp, rng):
    """variation.py: shuffle each module's per-run correct counts across run labels; p = share of draws whose run-total
    range is at least the observed one."""
    tot = [sum(x[i] for x in mod_tp) for i in range(len(mod_tp[0]))]
    obs = max(tot) - min(tot)
    hits = 0
    for _ in range(NDRAW):
        t = [0] * len(tot)
        for x in mod_tp:
            a = x[:]
            rng.shuffle(a)
            for i, v in enumerate(a):
                t[i] += v
        hits += (max(t) - min(t)) >= obs
    return obs, hits / NDRAW


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    X = {"v7": F.C7.runs(F.VERSION, F.REPS)}
    for k, (v, reps) in BASES.items():
        X[k] = F.C7.runs(v, reps)
    ok1 = [X["v6"][r]["correct"] for r in (0, 1, 2)] == [86, 83, 86] and [X["v5f"][r]["correct"] for r in range(6)] == [91, 85, 92, 94, 91, 88]
    print("self-test 1 (compare_v7's figures: v6 86/83/86; v5f 91/85/92/94/91/88):", "PASS" if ok1 else "FAIL")
    fails = F.CC.selftest()
    print("self-test 2 (compare_condensed.selftest: scorer = compare_v6.score, v6 vs itself clean, simulations):", "PASS" if not fails else f"FAIL {fails}")
    rng = random.Random(20261013)
    o, p, n = exact_p([3, 3, 3], [3, 3, 3])
    o2, p2, n2 = exact_p([9, 9, 9], [1, 1, 1])
    ok3 = p == 1.0 and abs(p2 - 1 / 20) < 1e-12 and n2 == 20
    print("self-test 3 (permutation code: equal groups p=1; separated 3v3 p=1/20):", "PASS" if ok3 else f"FAIL {p} {p2} {n2}")
    if not (ok1 and not fails and ok3):
        sys.exit("self-test failed: nothing written")
    out = {"scorer": "compare_condensed.score via compare_v7.runs (exact names, each reference entry used once, 109 findable per run)",
           "per run": {}, "pooled": {}, "tests": {}, "spread": {}}
    for k, x in X.items():
        out["per run"][k] = {f"r{r}": {"correct": y["correct"], "listed": y["listed"], "false positives": y["listed"] - y["correct"],
                                       "precision": round(y["correct"] / y["listed"], 3), "recall": round(y["correct"] / 109, 3)}
                             for r, y in x.items()}
        T, L = sum(y["correct"] for y in x.values()), sum(y["listed"] for y in x.values())
        out["pooled"][k] = {"precision": f"{T}/{L} = {T / L:.3f}", "recall": f"{T}/{109 * len(x)} = {T / (109 * len(x)):.3f}",
                            "correct per run mean": round(T / len(x), 2), "listed per run mean": round(L / len(x), 2)}
        cs = [y["correct"] for y in x.values()]
        ps = [y["correct"] / y["listed"] for y in x.values()]
        out["spread"][k] = {"correct range": [min(cs), max(cs)], "correct SD": round(st.pstdev(cs), 2),
                            "precision range": [round(min(ps), 3), round(max(ps), 3)]}
    v7 = X["v7"]
    # per module listed counts for the stratified precision test
    def per_mod(v, reps):
        return {m: [F.CC.score(v, r, m)[1::-1][:2] for r in reps] for m in F.MODS}   # (correct, listed)
    PM = {"v7": per_mod(F.VERSION, F.REPS)}
    for k, (v, reps) in BASES.items():
        PM[k] = per_mod(v, reps)
    for k in BASES:
        b = X[k]
        rec = exact_p([y["correct"] for y in v7.values()], [y["correct"] for y in b.values()])
        pre = exact_p([y["correct"] / y["listed"] for y in v7.values()], [y["correct"] / y["listed"] for y in b.values()])
        srec = strat_p(PM["v7"], PM[k], "recall", rng)
        spre = strat_p(PM["v7"], PM[k], "precision", rng)
        rng_b = out["spread"][k]["correct range"]
        out["tests"][f"v7 vs {k}"] = {
            "correct per run: mean difference": round(rec[0], 2), "run-level exact p (one-sided)": round(rec[1], 3), "splits": rec[2],
            "precision per run: mean difference": round(pre[0], 3), "precision run-level exact p (one-sided)": round(pre[1], 3),
            "module-stratified recall: pooled correct-per-run difference": round(srec[0], 2), "module-stratified recall p": round(srec[1], 4),
            "module-stratified precision: pooled difference": round(spre[0], 3), "module-stratified precision p": round(spre[1], 4),
            f"{k} run-to-run range of correct": rng_b,
            "v7 mean correct outside that range": not (rng_b[0] <= st.mean(y["correct"] for y in v7.values()) <= rng_b[1]),
        }
    mod_tp = [[v7[r]["per"][m] for r in F.REPS] for m in F.MODS]
    obs, p = within_p(mod_tp, rng)
    out["within v7"] = {"run-total range of correct": obs, "share of within-module shuffles with that range or more": round(p, 3),
                        "sum of module variances": round(sum(st.pvariance(x) for x in mod_tp), 2)}
    out["per module correct per run (v7)"] = {F.short(m): [v7[r]["per"][m] for r in F.REPS] for m in F.MODS}
    (F.HERE / "scores.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("pooled", "tests", "within v7", "spread")}, indent=1))


if __name__ == "__main__":
    main()
