"""Independent re-score of two_phase_v9k and two_phase_v9j (gpt-5.6-luna, high, r0-r2) on four module groups.

Exact scorer, per module and run: Counter of the listed names ("Asset RTL" of every row under "Assets"); the reference
rows (ground truth rows whose "element" is a name in chain.closed_names(module)) are walked in order; a row whose
element still has a copy in the Counter consumes one and counts correct. listed = number of asset rows; findable =
number of reference rows. Recall = correct / findable; precision = correct / listed. Pooled = sums over the three runs.

Nothing here calls an API, and none of the lab's run/compare scripts are imported. chain.py is imported only for
closed_names() (PIO_INPUT_VERSION=v1 is set first).
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
ROOT = Path(r"E:\jobs\ff\test\Prepoison_subset")
LAB = ROOT / "experiments" / "03_two_phase_csa_pio" / "lab"
sys.path.insert(0, str(LAB))
import chain  # noqa: E402

GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
RUNS = LAB / "runs"
MODEL_DIR = "gpt-5.6-luna__high"
VERSIONS = ("two_phase_v9k", "two_phase_v9j")
REPS = (0, 1, 2)
GATE_DP, GATE_DR = 0.05, -0.02

WATCH = [("neorv32_wdt", "reset_cause"), ("neorv32_wdt", "reset_wdt"), ("neorv32_gptmr", "irq_pnd"),
         ("neorv32_cpu_lsu", "mar"), ("neorv32_cpu_lsu", "amo_cmd"), ("neorv32_gpio", "port_in")]


def reference_rows(m: str) -> list:
    """Element names of the ground-truth rows of module m, in file order, kept when the element is a closed-set
    name (the second item of a chain.closed_names key)."""
    gt = json.loads(GT.read_text(encoding="utf-8"))["modules"]
    if m not in gt:
        return []
    names = {n for (_e, n) in chain.closed_names(m)}
    return [r["element"] for r in gt[m]["assets"] if r["element"] in names]


def listed_names(version: str, rep: int, m: str) -> list:
    p = RUNS / (version + "__v1") / MODEL_DIR / ("r%d" % rep) / "assets" / (m + ".json")
    return [a["Asset RTL"] for a in json.loads(p.read_text(encoding="utf-8"))["Assets"]]


def score(listed: list, ref: list) -> tuple:
    """(correct, listed, findable) by the exact rule in the module docstring."""
    copies = Counter(listed)
    correct = 0
    for el in ref:
        if copies[el] > 0:
            copies[el] -= 1
            correct += 1
    return correct, len(listed), len(ref)


def groups() -> dict:
    tun_dirs = sorted(d.name for d in (LAB / "inputs" / "v1" / "tuning").iterdir() if d.is_dir())
    held_dirs = sorted(d.name for d in (LAB / "inputs" / "v1" / "heldout").iterdir() if d.is_dir())
    no_ref = [m for m in tun_dirs if not reference_rows(m)]
    split = json.loads((LAB / "splits" / "tuning_v2.json").read_text(encoding="utf-8"))
    return {"tuning 15": [m for m in tun_dirs if m not in no_ref], "held-out 26": held_dirs,
            "tuning_v2": split["tuning"], "heldout_v2": split["heldout"],
            "_tuning folders with no reference row": no_ref}


def selftest() -> None:
    # synthetic: duplicates on both sides, one unlisted reference row, one extra listed name
    assert score(["a", "b", "b", "x"], ["a", "b", "b", "b", "c"]) == (3, 4, 5)
    assert score([], ["a"]) == (0, 0, 1)
    assert score(["a"], []) == (0, 1, 0)
    # hand-read from the files on 2026-10-18 (agent transcript): v9k r0
    assert score(listed_names("two_phase_v9k", 0, "neorv32_wdt"), reference_rows("neorv32_wdt")) == (8, 12, 8)
    assert score(listed_names("two_phase_v9k", 0, "neorv32_bus"), reference_rows("neorv32_bus")) == (10, 18, 11)
    assert score(listed_names("two_phase_v9k", 0, "neorv32_twi"), reference_rows("neorv32_twi")) == (6, 7, 8)
    assert reference_rows("neorv32_wdt") == ["ctrl.enable", "ctrl.lock", "ctrl.timeout", "cnt", "cnt_timeout",
                                             "reset_cause", "reset_wdt", "clkgen_en_o"]
    assert len(listed_names("two_phase_v9k", 0, "neorv32_wdt")) == 12


def main() -> None:
    selftest()
    print("SELFTEST PASS (3 synthetic + 3 hand-read module cases)")
    g = groups()
    print("tuning folders with no reference row:", g.pop("_tuning folders with no reference row"))
    for k, v in g.items():
        print("group %s: %d modules" % (k, len(v)))
    all_modules = sorted(set(sum(g.values(), [])))
    ref = {m: reference_rows(m) for m in all_modules}
    per = {}  # (version, rep, module) -> (correct, listed, findable)
    for v in VERSIONS:
        for r in REPS:
            for m in all_modules:
                per[(v, r, m)] = score(listed_names(v, r, m), ref[m])
    out = {"groups": {k: len(v) for k, v in g.items()}, "results": {}}
    pooled = {}
    for v in VERSIONS:
        print("\n== " + v)
        out["results"][v] = {}
        for gname, mods in g.items():
            rows = []
            C = L = F = 0
            for r in REPS:
                c = sum(per[(v, r, m)][0] for m in mods)
                l = sum(per[(v, r, m)][1] for m in mods)
                f = sum(per[(v, r, m)][2] for m in mods)
                C += c
                L += l
                F += f
                rows.append({"run": "r%d" % r, "correct": c, "listed": l, "findable": f,
                             "recall": round(c / f, 4), "precision": round(c / l, 4)})
                print("  %-12s r%d: correct %4d listed %4d findable %4d  recall %.4f  precision %.4f"
                      % (gname, r, c, l, f, c / f, c / l))
            pooled[(v, gname)] = (C, L, F)
            rows.append({"run": "pooled", "correct": C, "listed": L, "findable": F,
                         "recall": round(C / F, 4), "precision": round(C / L, 4)})
            print("  %-12s pooled: correct %4d listed %4d findable %4d  recall %.4f (%d/%d)  precision %.4f (%d/%d)"
                  % (gname, C, L, F, C / F, C, F, C / L, C, L))
            out["results"][v][gname] = rows
    # gate on pooled tuning_v2
    kC, kL, kF = pooled[("two_phase_v9k", "tuning_v2")]
    jC, jL, jF = pooled[("two_phase_v9j", "tuning_v2")]
    kP, kR, jP, jR = kC / kL, kC / kF, jC / jL, jC / jF
    p_ok, r_ok = kP >= jP + GATE_DP, kR >= jR + GATE_DR
    print("\n== gate (pooled tuning_v2)")
    print("  v9k precision %.4f vs v9j %.4f + %.2f = %.4f: %s (difference %+.4f)"
          % (kP, jP, GATE_DP, jP + GATE_DP, "PASS" if p_ok else "FAIL", kP - jP))
    print("  v9k recall    %.4f vs v9j %.4f - %.2f = %.4f: %s (difference %+.4f)"
          % (kR, jR, -GATE_DR, jR + GATE_DR, "PASS" if r_ok else "FAIL", kR - jR))
    print("  gate: " + ("PASS" if (p_ok and r_ok) else "FAIL"))
    out["gate"] = {"v9k_pooled_tuning_v2": {"precision": round(kP, 4), "recall": round(kR, 4)},
                   "v9j_pooled_tuning_v2": {"precision": round(jP, 4), "recall": round(jR, 4)},
                   "precision_bar": round(jP + GATE_DP, 4), "recall_bar": round(jR + GATE_DR, 4),
                   "precision_pass": p_ok, "recall_pass": r_ok, "pass": p_ok and r_ok}
    print("\n== watched names, v9k (copies listed per run)")
    out["watch"] = {}
    for m, n in WATCH:
        row = {}
        for r in REPS:
            row["r%d" % r] = Counter(listed_names("two_phase_v9k", r, m))[n]
        inref = n in ref[m]
        out["watch"][m + " " + n] = dict(row, in_reference=inref)
        print("  %-18s %-12s r0: %s  r1: %s  r2: %s   (reference row: %s)"
              % (m, n, row["r0"], row["r1"], row["r2"], "yes" if inref else "no"))
    (Path(__file__).parent / "rescore_result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nwrote", Path(__file__).parent / "rescore_result.json")


if __name__ == "__main__":
    main()
