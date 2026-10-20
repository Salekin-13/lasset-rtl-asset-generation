"""Independent re-score of two_phase_v9l and two_phase_v9j (r0-r2) on four module groups, with the pre-set gate.

Reads only: the manual reference, the stored assets/<module>.json files, the inputs/v1 folders, splits/tuning_v2.json
and chain.closed_names. No API call. No import of the lab's run or scoring scripts.

Exact scorer (as specified): per module and run, Counter of listed names ("Asset RTL"); reference rows walked in
order, a row whose element still has a copy consumes one and counts correct. listed = asset rows, findable = reference
rows (after the closed-set filter).

  python -B score_v9l.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
import chain  # noqa: E402

GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
RUNS = LAB / "runs"
MODEL_DIR = "gpt-5.6-luna__high"
VERSIONS = ("two_phase_v9l", "two_phase_v9j")
REPS = (0, 1, 2)
GATE_P = 0.05     # v9l pooled tuning_v2 precision >= v9j's + 0.05
GATE_R = -0.02    # v9l pooled tuning_v2 recall    >= v9j's - 0.02
NAMED = [("neorv32_wdt", "reset_cause"), ("neorv32_wdt", "reset_wdt"), ("neorv32_gptmr", "irq_pnd"),
         ("neorv32_cpu_lsu", "mar"), ("neorv32_cpu_lsu", "amo_cmd"), ("neorv32_gpio", "port_in")]


# ------------------------------------------------------------------------------------------- reference ---
def reference_rows(m: str, gt: dict) -> list[str]:
    """Reference elements of module m, in sheet order, kept only when the element is a name in the closed set."""
    names = {n for (_e, n) in chain.closed_names(m)}
    return [r["element"] for r in gt["modules"][m]["assets"] if r["element"] in names]


def listed_names(version: str, rep: int, m: str) -> list[str]:
    p = RUNS / f"{version}__v1" / MODEL_DIR / f"r{rep}" / "assets" / f"{m}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    return [a["Asset RTL"] for a in d["Assets"]]


def score(listed: list[str], reference: list[str]) -> tuple[int, int, int]:
    """(correct, listed, findable) by the exact scorer."""
    pool = Counter(listed)
    correct = 0
    for el in reference:
        if pool[el] > 0:
            pool[el] -= 1
            correct += 1
    return correct, len(listed), len(reference)


# ---------------------------------------------------------------------------------------------- groups ---
def groups(gt: dict) -> tuple[dict[str, list[str]], list[str]]:
    tuning_folders = sorted(p.name for p in (chain.INPUTS / "tuning").iterdir() if p.is_dir())
    heldout_folders = sorted(p.name for p in (chain.INPUTS / "heldout").iterdir() if p.is_dir())
    no_ref = [m for m in tuning_folders if m not in gt["modules"] or not reference_rows(m, gt)]
    split = json.loads((LAB / "splits" / "tuning_v2.json").read_text(encoding="utf-8"))
    g = {"tuning 15": [m for m in tuning_folders if m not in no_ref],
         "held-out 26": heldout_folders,
         "tuning_v2": list(split["tuning"]),
         "heldout_v2": list(split["heldout"])}
    return g, no_ref


# -------------------------------------------------------------------------------------------- self-test ---
def selftest(gt: dict) -> list[str]:
    fails = []

    def check(label, cond):
        if not cond:
            fails.append(label)

    # 1. the scorer on a hand-built case: duplicates consume one copy each, extras are not correct
    check("scorer hand case", score(["a", "a", "b", "x"], ["a", "a", "a", "c"]) == (2, 4, 4))
    check("scorer empty listed", score([], ["a"]) == (0, 0, 1))
    check("scorer empty reference", score(["a"], []) == (0, 1, 0))
    # 2. hand-read reference rows of neorv32_wdt (data/ground_truth/manual_gt_neorv32.json, "neorv32_wdt" -> assets,
    #    elements read by hand: ctrl.enable, ctrl.lock, ctrl.timeout, cnt, cnt_timeout, reset_cause, reset_wdt,
    #    clkgen_en_o); all eight are names in the closed set, so the filter keeps all eight in order
    check("wdt reference rows", reference_rows("neorv32_wdt", gt) ==
          ["ctrl.enable", "ctrl.lock", "ctrl.timeout", "cnt", "cnt_timeout", "reset_cause", "reset_wdt", "clkgen_en_o"])
    # 3. hand-read listed names of two_phase_v9l r0 neorv32_wdt (runs/two_phase_v9l__v1/gpt-5.6-luna__high/r0/assets/
    #    neorv32_wdt.json): the first six "Asset RTL" values, read by hand
    check("v9l r0 wdt first six listed", listed_names("two_phase_v9l", 0, "neorv32_wdt")[:6] ==
          ["ctrl.enable", "clkgen_en_o", "ctrl.lock", "ctrl.timeout", "cnt", "cnt_timeout"])
    # 4. the filter drops a reference element that is not a closed-set name
    check("filter drops unknown element", "zzz_not_a_name" not in {n for (_e, n) in chain.closed_names("neorv32_wdt")})
    # 5. group sizes: 17 tuning folders of which 2 have no reference row, 26 held-out folders, 27 + 14 in tuning_v2
    g, no_ref = groups(gt)
    check("two tuning folders without reference", len(no_ref) == 2 and len(g["tuning 15"]) == 15)
    check("held-out 26", len(g["held-out 26"]) == 26)
    check("tuning_v2 27 / heldout_v2 14", len(g["tuning_v2"]) == 27 and len(g["heldout_v2"]) == 14)
    check("tuning_v2 + heldout_v2 = all 41", sorted(g["tuning_v2"] + g["heldout_v2"]) == sorted(gt["modules"]))
    check("tuning 15 + held-out 26 = all 41", sorted(g["tuning 15"] + g["held-out 26"]) == sorted(gt["modules"]))
    return fails


# ------------------------------------------------------------------------------------------------- main ---
def main() -> int:
    gt = json.loads(GT.read_text(encoding="utf-8"))
    fails = selftest(gt)
    if fails:
        print("SELF-TEST FAILED:", fails)
        print("nothing reported from this run")
        return 1
    print("self-test PASS (11 checks)")
    g, no_ref = groups(gt)
    print("tuning folders without a reference row (excluded):", no_ref)

    # per module scores, then per group / run / version
    ref = {m: reference_rows(m, gt) for m in gt["modules"]}
    dropped = {m: len(gt["modules"][m]["assets"]) - len(ref[m]) for m in gt["modules"]}
    print("reference rows dropped by the closed-set filter (module: dropped/raw):",
          {m: f"{dropped[m]}/{len(gt['modules'][m]['assets'])}" for m in gt["modules"] if dropped[m]})
    per_module = {}   # (version, rep, module) -> (correct, listed, findable)
    for v in VERSIONS:
        for r in REPS:
            for m in gt["modules"]:
                per_module[(v, r, m)] = score(listed_names(v, r, m), ref[m])

    out = {"versions": {}, "groups": g, "excluded tuning folders": no_ref}
    for v in VERSIONS:
        out["versions"][v] = {}
        for gname, mods in g.items():
            rows = {}
            C = L = F = 0
            for r in REPS:
                c = sum(per_module[(v, r, m)][0] for m in mods)
                n_listed = sum(per_module[(v, r, m)][1] for m in mods)
                f = sum(per_module[(v, r, m)][2] for m in mods)
                rows[f"r{r}"] = {"correct": c, "listed": n_listed, "findable": f,
                                 "recall": c / f if f else None, "precision": c / n_listed if n_listed else None}
                C += c
                L += n_listed
                F += f
            rows["pooled"] = {"correct": C, "listed": L, "findable": F,
                              "recall": C / F if F else None, "precision": C / L if L else None}
            out["versions"][v][gname] = rows

    # print tables
    for v in VERSIONS:
        print(f"\n== {v} ==")
        for gname in g:
            print(f"  [{gname}] ({len(g[gname])} modules)")
            for k, x in out["versions"][v][gname].items():
                print(f"    {k:7s} correct {x['correct']:4d}  listed {x['listed']:4d}  findable {x['findable']:4d}  "
                      f"recall {x['recall']:.3f}  precision {x['precision']:.3f}")

    # the gate on pooled tuning_v2
    vl = out["versions"]["two_phase_v9l"]["tuning_v2"]["pooled"]
    vj = out["versions"]["two_phase_v9j"]["tuning_v2"]["pooled"]
    dp = vl["precision"] - vj["precision"]
    dr = vl["recall"] - vj["recall"]
    gate_p = vl["precision"] >= vj["precision"] + GATE_P
    gate_r = vl["recall"] >= vj["recall"] + GATE_R
    out["gate"] = {"v9l pooled tuning_v2 precision": vl["precision"],
                   "v9j pooled tuning_v2 precision": vj["precision"],
                   "precision delta": dp, "precision bar (+0.05) met": gate_p,
                   "v9l pooled tuning_v2 recall": vl["recall"], "v9j pooled tuning_v2 recall": vj["recall"],
                   "recall delta": dr, "recall bar (-0.02) met": gate_r, "gate pass": gate_p and gate_r}
    print("\n== gate (pooled tuning_v2, three runs) ==")
    print(f"  precision: v9l {vl['correct']}/{vl['listed']} = {vl['precision']:.4f}  vs  v9j {vj['correct']}/{vj['listed']}"
          f" = {vj['precision']:.4f}  delta {dp:+.4f}  need >= +{GATE_P}: {'MET' if gate_p else 'NOT MET'}")
    print(f"  recall:    v9l {vl['correct']}/{vl['findable']} = {vl['recall']:.4f}  vs  v9j {vj['correct']}/{vj['findable']}"
          f" = {vj['recall']:.4f}  delta {dr:+.4f}  need >= {GATE_R}: {'MET' if gate_r else 'NOT MET'}")
    print(f"  gate: {'PASS' if gate_p and gate_r else 'FAIL'}")

    # named assets per v9l run
    out["named assets (v9l)"] = {}
    print("\n== named assets listed by two_phase_v9l (copies in the assets file per run; in reference: yes/no) ==")
    for m, el in NAMED:
        in_ref = el in ref[m]
        per_run = {}
        for r in REPS:
            per_run[f"r{r}"] = Counter(listed_names("two_phase_v9l", r, m))[el]
        out["named assets (v9l)"][f"{m} {el}"] = {"in reference": in_ref, **per_run}
        words = []
        for r in REPS:
            words.append(f"r{r}: " + ("listed" if per_run[f"r{r}"] else "NOT listed"))
        print(f"  {m:18s} {el:12s} in reference: {'yes' if in_ref else 'no':3s}  " + "  ".join(words))

    (HERE / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
