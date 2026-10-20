"""Re-score two_phase_p1o_first, two_phase_v9n_place and two_phase_v9j on the held-out 26 with the exact scorer.

Independent of every other reader script: only chain.closed_names and chain.run_dir are imported.
No API call is made. Run with: python -B rescore_tier3.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
LAB = Path(__file__).resolve().parents[3]            # .../experiments/03_two_phase_csa_pio/lab
ROOT = LAB.parents[2]                                # .../Prepoison_subset
sys.path.insert(0, str(LAB))
import chain  # noqa: E402   (closed_names, run_dir only)

GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
HELDOUT = LAB / "inputs" / "v1" / "heldout"
MODEL, EFFORT = "gpt-5.6-luna", "high"
VERSIONS = ("two_phase_p1o_first", "two_phase_v9n_place", "two_phase_v9j")
RUNS = (0, 1, 2)
DEBUG = "neorv32_debug_dm"


# ------------------------------------------------------------------------------------------------ scorer ---
def score(listed: list[str], reference: list[str]) -> tuple[int, list[bool]]:
    """Exact scorer. Counter of listed names; reference rows walked in order; a row whose element still has a
    copy consumes one and counts correct. Returns (correct, per-reference-row hit flags)."""
    pool = Counter(listed)
    hits = []
    for el in reference:
        if pool[el] > 0:
            pool[el] -= 1
            hits.append(True)
        else:
            hits.append(False)
    return sum(hits), hits


def selftest() -> None:
    # duplicates in the reference: two copies of "a" need two listed copies
    c, h = score(["a", "b", "x"], ["a", "a", "b", "c"])
    assert (c, h) == (2, [True, False, True, False]), (c, h)
    c, h = score(["a", "a", "b"], ["a", "a", "b", "c"])
    assert (c, h) == (3, [True, True, True, False]), (c, h)
    # extra listed copies do not add correct; empty lists score 0
    c, h = score(["a", "a", "a"], ["a"])
    assert (c, h) == (1, [True]), (c, h)
    assert score([], ["a"]) == (0, [False])
    assert score(["a"], []) == (0, [])
    print("scorer self-test: PASS (5 hand-made cases)")


# ------------------------------------------------------------------------------------------------ inputs ---
def heldout_modules() -> list[str]:
    return sorted(p.name for p in HELDOUT.iterdir() if p.is_dir())


def reference_rows(gt: dict, m: str) -> list[str]:
    """Reference elements of module m that are names in the closed set, in sheet order, duplicates kept."""
    names = {k[1] for k in chain.closed_names(m)}
    rows = gt["modules"][m]["assets"]
    return [r["element"] for r in rows if r["element"] in names]


def listed_names(version: str, rep: int, m: str) -> list[str] | None:
    p = chain.run_dir(version, MODEL, rep, EFFORT) / "assets" / f"{m}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return [r["Asset RTL"] for r in d["Assets"]]


def asset_file_count(version: str, rep: int) -> int | None:
    d = chain.run_dir(version, MODEL, rep, EFFORT) / "assets"
    if not d.is_dir():
        return None
    return len([p for p in d.iterdir() if p.suffix == ".json"])


# ------------------------------------------------------------------------------------------------ main ---
def main() -> None:
    selftest()
    gt = json.loads(GT.read_text(encoding="utf-8"))
    mods = heldout_modules()
    print(f"held-out modules: {len(mods)}")
    ref = {m: reference_rows(gt, m) for m in mods}
    raw = {m: len(gt["modules"][m]["assets"]) for m in mods}
    findable_all = sum(len(v) for v in ref.values())
    print(f"reference rows on the held-out 26: {sum(raw.values())} raw, {findable_all} in the closed set (findable)")
    print()

    # per version / run / module: listed names, hits
    table = {}      # (version, rep) -> dict(correct, listed, findable, modules)
    hits = {}       # (version, rep) -> {(m, i): bool}  i = index of the reference row within the module
    lists = {}      # (version, rep) -> {m: list of listed names}
    for v in VERSIONS:
        for k in RUNS:
            n = asset_file_count(v, k)
            if n is None:
                print(f"{v} r{k}: no assets folder")
                continue
            present = [m for m in mods if (chain.run_dir(v, MODEL, k, EFFORT) / "assets" / f"{m}.json").exists()]
            print(f"{v} r{k}: {n} asset files in folder, {len(present)} of the held-out 26 present")
            if not present:
                continue
            c_tot = l_tot = f_tot = 0
            hh, ll = {}, {}
            for m in mods:
                names = listed_names(v, k, m)
                if names is None:
                    continue           # a missing module: counted in neither numerator nor denominator
                c, h = score(names, ref[m])
                c_tot += c
                l_tot += len(names)
                f_tot += len(ref[m])
                ll[m] = names
                for i, flag in enumerate(h):
                    hh[(m, i)] = flag
            table[(v, k)] = dict(correct=c_tot, listed=l_tot, findable=f_tot, modules=len(present))
            hits[(v, k)] = hh
            lists[(v, k)] = ll
    print()

    # per-run and pooled table
    pooled = {}
    print(f"{'version':22s} {'run':6s} {'correct':>8s} {'listed':>7s} {'findable':>9s} {'recall':>7s} {'precision':>10s}")
    for v in VERSIONS:
        reps = [k for k in RUNS if (v, k) in table]
        pc = pl = pf = 0
        for k in reps:
            t = table[(v, k)]
            r = t["correct"] / t["findable"] if t["findable"] else float("nan")
            p = t["correct"] / t["listed"] if t["listed"] else float("nan")
            print(f"{v:22s} r{k:<5d} {t['correct']:8d} {t['listed']:7d} {t['findable']:9d} {r:7.3f} {p:10.3f}")
            pc += t["correct"]
            pl += t["listed"]
            pf += t["findable"]
        if reps:
            r = pc / pf if pf else float("nan")
            p = pc / pl if pl else float("nan")
            pooled[v] = dict(correct=pc, listed=pl, findable=pf, recall=r, precision=p, runs=reps)
            runs_txt = ", ".join("r%d" % k for k in reps)
            print(f"{v:22s} {'pooled':6s} {pc:8d} {pl:7d} {pf:9d} {r:7.3f} {p:10.3f}   (runs {runs_txt})")
    print()

    # the pre-set cut
    a, b = pooled.get("two_phase_p1o_first"), pooled.get("two_phase_v9n_place")
    if a and b:
        d_r = a["recall"] - b["recall"]
        d_p = a["precision"] - b["precision"]
        ok_r = d_r >= -0.02
        ok_p = d_p >= 0.0
        print(f"cut: p1o_first pooled recall {a['recall']:.4f} vs v9n_place {b['recall']:.4f}: delta {d_r:+.4f} "
              f"-> {'PASS' if ok_r else 'FAIL'} (allowed down to -0.02)")
        print(f"cut: p1o_first pooled precision {a['precision']:.4f} vs v9n_place {b['precision']:.4f}: delta {d_p:+.4f} "
              f"-> {'PASS' if ok_p else 'FAIL'} (not below)")
        print(f"cut overall: {'PASS' if ok_r and ok_p else 'FAIL'}")
    print()

    # debug module per version and run
    print(f"{DEBUG}: reference rows in closed set = {len(ref[DEBUG])}: {ref[DEBUG]}")
    for v in VERSIONS:
        for k in RUNS:
            if (v, k) not in lists or DEBUG not in lists[(v, k)]:
                continue
            names = lists[(v, k)][DEBUG]
            c, h = score(names, ref[DEBUG])
            found = [e for e, f in zip(ref[DEBUG], h) if f]
            print(f"  {v:22s} r{k}: listed {len(names):3d}, correct {c} {found}")
    print()

    # reference entries found in all three v9n_place runs but in at most one p1o_first run
    vb = [hits[("two_phase_v9n_place", k)] for k in RUNS if ("two_phase_v9n_place", k) in hits]
    va = [hits[("two_phase_p1o_first", k)] for k in RUNS if ("two_phase_p1o_first", k) in hits]
    print(f"v9n_place runs scored: {len(vb)}; p1o_first runs scored: {len(va)}")
    keys = sorted({key for h in vb for key in h} | {key for h in va for key in h})
    lost = []
    for key in keys:
        nb = sum(1 for h in vb if h.get(key, False))
        na = sum(1 for h in va if h.get(key, False))
        if nb == len(vb) == 3 and na <= 1:
            lost.append((key, na))
    print(f"reference entries found in all 3 v9n_place runs but in at most 1 p1o_first run: {len(lost)}")
    for (m, i), na in lost:
        print(f"  {m:26s} {ref[m][i]:40s} (row {i}; p1o_first found it in {na} run(s))")
    print()

    # names p1o_first lists in at least two runs that v9n_place never lists
    la = [lists[("two_phase_p1o_first", k)] for k in RUNS if ("two_phase_p1o_first", k) in lists]
    lb = [lists[("two_phase_v9n_place", k)] for k in RUNS if ("two_phase_v9n_place", k) in lists]
    seen_b = {(m, n) for L in lb for m, names in L.items() for n in names}
    cnt_a = Counter()
    for L in la:
        for m, names in L.items():
            for n in set(names):
                cnt_a[(m, n)] += 1
    extra = sorted((m, n, c) for (m, n), c in cnt_a.items() if c >= 2 and (m, n) not in seen_b)
    print(f"names p1o_first lists in >=2 runs that v9n_place never lists: {len(extra)}")
    ref_set = {(m, e) for m in mods for e in ref[m]}
    for m, n, c in extra:
        tag = "in reference" if (m, n) in ref_set else "not in reference"
        print(f"  {m:26s} {n:40s} listed in {c} p1o_first run(s); {tag}")


if __name__ == "__main__":
    main()
