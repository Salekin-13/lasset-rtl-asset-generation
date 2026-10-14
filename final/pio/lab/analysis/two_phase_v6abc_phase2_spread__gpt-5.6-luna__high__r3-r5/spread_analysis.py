"""Phase 2's own run-to-run spread on fixed concepts, and the paired comparisons read against it. Read-only; writes
spread_result.json.

Pairs that share their Phase 1 replies (so they differ only by the Phase 2 call):
  yardstick   v6abc r3 vs r0, r4 vs r1, r5 vs r2: the same Phase 2 prompt drawn twice (run_spread.py)
  v6d         v6d rX vs v6abc rX: v6abc's Phase 2 with one unit restored
  v6b         v6b rX vs v6 rX: v6's Phase 2 condensed (Phase 1 = v6's)
  v6e         v6e rX vs v6 rX: v6's Phase 2 with part of v6b's condensing
Per pair: correct finds of each side, their difference, and the sizes of the symmetric differences of the correct-find
sets and of the listed-primary sets (exact scorer of compare_condensed.py). A comparison is "within the spread" when its
differences fall inside the range of the yardstick's three pairs.

  python spread_analysis.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2"))
import compare_condensed as CC  # noqa: E402


def run_sets(v, r):
    T = L = 0
    cs, ls, per = set(), set(), {}
    for m in CC.MODS:
        l, t, f, s = CC.score(v, r, m)
        T, L = T + t, L + l
        cs |= set(f)
        ls |= s
        per[m] = t
    return {"correct": T, "listed": L, "cset": cs, "lset": ls, "per module": per}


def pair(a, b):
    """a, b: (version, rep). b is the reference side."""
    x, y = run_sets(*a), run_sets(*b)
    mods = {m.replace("neorv32_", ""): x["per module"][m] - y["per module"][m] for m in CC.MODS
            if x["per module"][m] != y["per module"][m]}
    return {"pair": f"{a[0].replace('two_phase_', '')} r{a[1]} vs {b[0].replace('two_phase_', '')} r{b[1]}",
            "correct": (x["correct"], y["correct"]), "difference": x["correct"] - y["correct"],
            "correct sets differ by": len(x["cset"] ^ y["cset"]), "listed sets differ by": len(x["lset"] ^ y["lset"]),
            "modules changed (correct)": mods}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups = {
        "yardstick: v6abc Phase 2 drawn again": [(("two_phase_v6abc", r + 3), ("two_phase_v6abc", r)) for r in CC.REPS],
        "v6d vs v6abc (one unit restored)": [(("two_phase_v6d", r), ("two_phase_v6abc", r)) for r in CC.REPS],
        "v6b vs v6 (Phase 2 condensed)": [(("two_phase_v6b", r), ("two_phase_v6", r)) for r in CC.REPS],
        "v6e vs v6 (part of v6b's condensing)": [(("two_phase_v6e", r), ("two_phase_v6", r)) for r in CC.REPS],
    }
    out = {}
    for g, pairs in groups.items():
        rows = []
        for a, b in pairs:
            try:
                rows.append(pair(a, b))
            except FileNotFoundError as e:
                rows.append({"pair": f"{a} vs {b}", "missing": str(e)})
        out[g] = rows
        print(f"\n== {g}")
        for r in rows:
            if "missing" in r:
                print(f"  {r['pair']}: MISSING {r['missing'][:90]}")
                continue
            print(f"  {r['pair']}: correct {r['correct'][0]} vs {r['correct'][1]} ({r['difference']:+d}); correct sets differ by "
                  f"{r['correct sets differ by']}, listed by {r['listed sets differ by']}; modules {r['modules changed (correct)']}")
    ys = [r for r in out["yardstick: v6abc Phase 2 drawn again"] if "missing" not in r]
    if len(ys) == 3:
        rng = lambda k: (min(abs(r[k]) for r in ys), max(abs(r[k]) for r in ys))
        print("\nyardstick range: |difference|", rng("difference"), "| correct sets", rng("correct sets differ by"),
              "| listed sets", rng("listed sets differ by"))
        for g in list(groups)[1:]:
            rows = [r for r in out[g] if "missing" not in r]
            inside = [abs(r["difference"]) <= rng("difference")[1] and r["correct sets differ by"] <= rng("correct sets differ by")[1]
                      for r in rows]
            print(f"  {g}: {sum(inside)} of {len(rows)} pairs within the yardstick's largest difference")
    (HERE / "spread_result.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
