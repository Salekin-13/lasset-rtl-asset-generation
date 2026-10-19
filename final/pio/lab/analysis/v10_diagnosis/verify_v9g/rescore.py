"""Independent exact re-scorer for the held-out runs of two_phase_v9g / v9f / v9.

Does not import any lab code. Reads the raw JSON files only. Never calls an API.
"""
import json
import os
import sys
from collections import Counter

ROOT = r"E:\jobs\ff\test\Prepoison_subset"
LAB = os.path.join(ROOT, "final", "pio", "lab")
GT_PATH = os.path.join(ROOT, "data", "ground_truth", "manual_gt_neorv32.json")
HELDOUT_DIR = os.path.join(LAB, "inputs", "v1", "heldout")
RUNS_DIR = os.path.join(LAB, "runs")
MODEL_DIR = "gpt-5.6-luna__high"
VERSIONS = ["two_phase_v9g", "two_phase_v9f", "two_phase_v9"]
RUNS = ["r0", "r1", "r2"]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def score_module(listed_names, ref_elements):
    """Exact scorer.

    listed_names: list of strings (one per asset row, duplicates kept)
    ref_elements: list of strings (one per reference row, in order)
    returns (correct, listed, findable)
    """
    left = Counter(listed_names)
    correct = 0
    for el in ref_elements:
        if left[el] > 0:
            left[el] -= 1
            correct += 1
    return correct, len(listed_names), len(ref_elements)


def self_test():
    # Synthetic case, answer known by construction.
    # ref has 'a' twice, 'b' once, 'c' once; listed has 'a' once, 'b' twice, 'x' once.
    # 'a' matches 1 of 2 rows, 'b' matches 1 (second copy unused), 'c' none, 'x' is extra.
    c, l, f = score_module(["a", "b", "b", "x"], ["a", "b", "a", "c"])
    assert (c, l, f) == (2, 4, 4), (c, l, f)
    # Empty listed
    assert score_module([], ["a"]) == (0, 0, 1)
    # Exact: case and whitespace differ -> no match
    assert score_module(["A", " b"], ["a", "b"]) == (0, 2, 2)
    # Duplicate listed copies each consume a reference row
    assert score_module(["a", "a"], ["a", "a", "a"]) == (2, 2, 3)
    return True


def record_ports(closed_set):
    """Set of port names that have a non-empty 'record type', over all entities."""
    out = set()
    for ent in closed_set.get("entity list", []):
        for p in ent.get("port list", []):
            if p.get("record type"):
                out.add(p["port"])
    return out


def main():
    assert self_test()
    gt = load_json(GT_PATH)["modules"]
    modules = sorted(
        d for d in os.listdir(HELDOUT_DIR)
        if os.path.isdir(os.path.join(HELDOUT_DIR, d)) and d.startswith("neorv32_")
    )
    assert len(modules) == 26, len(modules)
    missing_gt = [m for m in modules if m not in gt]
    assert not missing_gt, missing_gt

    rec_ports = {m: record_ports(load_json(os.path.join(HELDOUT_DIR, m, "closed_set.json")))
                 for m in modules}
    ref = {m: [row["element"] for row in gt[m]["assets"]] for m in modules}
    findable_total = sum(len(ref[m]) for m in modules)

    figures = {}
    problems = []
    hygiene = {}  # how many listed names would change under strip/casefold (exactness check)

    for ver in VERSIONS:
        figures[ver] = {}
        pooled = Counter()
        for run in RUNS:
            adir = os.path.join(RUNS_DIR, f"{ver}__v1", MODEL_DIR, run, "assets")
            tot = Counter()
            dot_rec = 0
            dot_any = 0
            per_mod = {}
            nonexact = 0
            for m in modules:
                path = os.path.join(adir, m + ".json")
                if not os.path.exists(path):
                    problems.append(f"{ver} {run}: missing assets file for {m}")
                    continue
                data = load_json(path)
                rows = data["Assets"]
                names = [r["Asset RTL"] for r in rows]
                for n in names:
                    if not isinstance(n, str):
                        problems.append(f"{ver} {run} {m}: non-string Asset RTL {n!r}")
                    elif n != n.strip() or n != n.lower():
                        nonexact += 1
                c, l, f = score_module(names, ref[m])
                per_mod[m] = (c, l, f)
                tot["correct"] += c
                tot["listed"] += l
                tot["findable"] += f
                for n in names:
                    if isinstance(n, str) and "." in n:
                        dot_any += 1
                        if n.split(".", 1)[0] in rec_ports[m]:
                            dot_rec += 1
            assert tot["findable"] == findable_total, (tot["findable"], findable_total)
            figures[ver][run] = {
                "correct": tot["correct"],
                "listed": tot["listed"],
                "findable": tot["findable"],
                "recall": round(tot["correct"] / tot["findable"], 4) if tot["findable"] else None,
                "precision": round(tot["correct"] / tot["listed"], 4) if tot["listed"] else None,
                "dotted_listed_names": dot_any,
                "dotted_names_with_record_port_prefix": dot_rec,
                "modules_scored": len(per_mod),
            }
            hygiene[(ver, run)] = nonexact
            pooled["correct"] += tot["correct"]
            pooled["listed"] += tot["listed"]
            pooled["findable"] += tot["findable"]
            pooled["dot_any"] += dot_any
            pooled["dot_rec"] += dot_rec
        figures[ver]["pooled_r0_r2"] = {
            "correct": pooled["correct"],
            "listed": pooled["listed"],
            "findable": pooled["findable"],
            "recall": round(pooled["correct"] / pooled["findable"], 4),
            "precision": round(pooled["correct"] / pooled["listed"], 4),
            "dotted_listed_names": pooled["dot_any"],
            "dotted_names_with_record_port_prefix": pooled["dot_rec"],
        }

    figures["_meta"] = {
        "heldout_modules": len(modules),
        "findable_per_run": findable_total,
        "listed_names_not_stripped_or_not_lowercase": {f"{v} {r}": n for (v, r), n in hygiene.items()},
    }
    print(json.dumps(figures, indent=1))
    if problems:
        print("PROBLEMS:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)

    # Hand-check print: gpio reference vs v9g r0 listing, for a manual tally.
    m = "neorv32_gpio"
    print("\nHAND CHECK neorv32_gpio reference rows:", ref[m])
    for ver in VERSIONS:
        names = [r["Asset RTL"] for r in load_json(
            os.path.join(RUNS_DIR, f"{ver}__v1", MODEL_DIR, "r0", "assets", m + ".json"))["Assets"]]
        print(f"  {ver} r0 listed:", names, "->", score_module(names, ref[m]))


if __name__ == "__main__":
    main()
