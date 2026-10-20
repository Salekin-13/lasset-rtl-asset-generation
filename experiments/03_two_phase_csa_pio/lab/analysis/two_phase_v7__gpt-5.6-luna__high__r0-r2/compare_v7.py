"""two_phase_v7 (v6d + five narrowings: CX2.U3b, CX4.TF1, CX1-ACF, P11.5, LS1) against v6 (3 runs), v6d (3 runs) and
v5f (6 runs). The narrowings target the recall v6 lost against v5f (pooled 0.827 -> 0.780) while keeping v6's precision
(0.416 -> 0.620). Read-only on stored files; writes compare_v7.json.

Exact scorer of compare_condensed.py (names equal, each reference entry used once; 109 findable per run). Reports:
  - completeness (all 15 modules, nothing pending);
  - per run and pooled precision (correct / listed) and recall (correct / 109);
  - the readings set in prompts/two_phase_v7/README.md before the run;
  - the 10 elements v6 lost (found in 5 or more of v5f's 6 runs and 2 or more of v5g's 3, but in at most 1 v6 run):
    in how many v7 runs each is found;
  - a module-level sign test (per module, correct summed over the runs, version against v6; losses cluster by reply, so
    elements are not independent);
  - watch-list false positives: listed elements that are not reference finds and whose names look like the kinds the
    v6 diagnosis expected to come back (state registers, busy flags, locked bits, keeper busy or lock, cache tag or
    index). This is a name pattern, so it is approximate.

Self-test: v6 correct 86/83/86 and v5f r0-r5 correct 91/85/92/94/91/88, as re-derived on 2026-10-13.

  python compare_v7.py
"""
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2"))
import compare_condensed as CC  # noqa: E402

LOST10 = ["bus:a_req#1", "bus:b_req#1", "bus:state#1", "bus:state#2", "cpu_cp_cfu:csr_addr_i#1", "cpu_cp_cfu:csr_we_i#1",
          "cpu_cp_muldiv:ctrl.state#1", "cpu_cp_muldiv:valid_o#1", "imem:addr#1", "sys:enable_i#1"]
WATCH = re.compile(r"(^|[.:_])(state|busy|locked|lock|tag|idx)$")
VERS = {"v7": ("two_phase_v7", (0, 1, 2)), "v6d": ("two_phase_v6d", (0, 1, 2)), "v6": ("two_phase_v6", (0, 1, 2)),
        "v5f": ("two_phase_v5f", (0, 1, 2, 3, 4, 5))}


def runs(v, reps):
    out = {}
    for r in reps:
        T = L = 0
        cs, ls, per = set(), set(), {}
        for m in CC.MODS:
            l, t, f, s = CC.score(v, r, m)
            T, L = T + t, L + l
            cs |= set(f)
            ls |= s
            per[m] = t
        out[r] = {"correct": T, "listed": L, "cset": cs, "lset": ls, "per": per}
    return out


def sign_p(a, b):
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n)


def watch_fps(x):
    """Listed elements matching the watch pattern that are not reference finds, per run."""
    out = {}
    for r, y in x.items():
        correct_names = {e.split("#")[0] for e in y["cset"]}
        out[r] = sorted(e for e in y["lset"] if WATCH.search(e.split(":", 1)[1]) and e not in correct_names)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    X = {}
    for k, (v, reps) in VERS.items():
        c = CC.complete(v) if k == "v7" else None
        if c and not all(c[r]["assets files"] == len(CC.MODS) and c[r]["pending"] == 0 for r in reps):
            print("v7 incomplete:", json.dumps(c))
            if k == "v7":
                X[k] = None
                continue
        X[k] = runs(v, reps)
    ok = [X["v6"][r]["correct"] for r in (0, 1, 2)] == [86, 83, 86] and \
         [X["v5f"][r]["correct"] for r in range(6)] == [91, 85, 92, 94, 91, 88]
    print("self-test (v6 86/83/86; v5f 91/85/92/94/91/88):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    if X.get("v7") is None:
        print("v7 not run yet or incomplete; nothing read")
        return
    rep = {}
    for k, x in X.items():
        T = sum(y["correct"] for y in x.values())
        L = sum(y["listed"] for y in x.values())
        n = 109 * len(x)
        rep[k] = {"per run": {r: (y["correct"], y["listed"], round(y["correct"] / y["listed"], 3), round(y["correct"] / 109, 3)) for r, y in x.items()},
                  "pooled precision": f"{T}/{L} = {T / L:.3f}", "pooled recall": f"{T}/{n} = {T / n:.3f}"}
        print(f"{k:4s} per run (correct, listed, P, R): {rep[k]['per run']} | pooled P {rep[k]['pooled precision']}, R {rep[k]['pooled recall']}")
    v7 = X["v7"]
    found = {e: sum(e in y["cset"] for y in v7.values()) for e in LOST10}
    rec = [e for e, n in found.items() if n >= 2]
    print(f"\nthe 10 elements v6 lost: found in 2 or more v7 runs: {len(rec)} of 10")
    for e, n in found.items():
        print(f"  {e}: v7 {n} of 3")
    R = {r: v7[r]["correct"] / 109 for r in v7}
    Pv = {r: v7[r]["correct"] / v7[r]["listed"] for r in v7}
    readings = {
        "1. recovered (2+ of 3 runs) at least 5 of the 10": f"{len(rec)} of 10 -> {'held' if len(rec) >= 5 else 'FALSIFIED'}",
        "2. recall below 0.761 (v6's lowest) in 2+ runs": f"runs {[r for r in R if R[r] < 0.761]} -> {'FALSIFIED' if sum(R[r] < 0.761 for r in R) >= 2 else 'held'}",
        "2b. recall above 0.789 (v6's highest) in 2+ runs (supports a gain)": f"runs {[r for r in R if R[r] > 0.789]} -> {'yes' if sum(R[r] > 0.789 for r in R) >= 2 else 'no'}",
        "3. precision below 0.601 (v6's lowest) in 2+ runs": f"runs {[r for r in Pv if Pv[r] < 0.601]} -> {'FALSIFIED' if sum(Pv[r] < 0.601 for r in Pv) >= 2 else 'held'}",
    }
    print("\nREADINGS (prompts/two_phase_v7/README.md)")
    for k, v in readings.items():
        print(f"  {k}: {v}")
    for base in ("v6", "v6d"):
        up = sum(sum(v7[r]["per"][m] for r in v7) > sum(X[base][r]["per"][m] for r in X[base]) for m in CC.MODS)
        dn = sum(sum(v7[r]["per"][m] for r in v7) < sum(X[base][r]["per"][m] for r in X[base]) for m in CC.MODS)
        print(f"module-level vs {base}: modules up {up}, down {dn}, sign test p = {sign_p(up, dn):.2f}")
    wv7, wv6 = watch_fps(v7), watch_fps(X["v6"])
    print(f"\nwatch-list false positives per run: v7 {[len(v) for v in wv7.values()]}, v6 {[len(v) for v in wv6.values()]}")
    new = sorted(set().union(*wv7.values()) - set().union(*wv6.values()))
    print("  in v7 but in no v6 run:", new)
    out = {"report": rep, "lost10": found, "readings": readings, "watch v7": wv7, "watch v6": wv6}
    (HERE / "compare_v7.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
