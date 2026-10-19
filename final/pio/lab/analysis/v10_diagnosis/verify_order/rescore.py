"""Independent exact re-score of two_phase_v9i and two_phase_v9i_orderB, runs r0-r2, seven held-out modules.

Written from the task spec only. Does not import chain.py, labkit.py, run_order.py or src/eval_assets.py.

Scoring rule (per module, per run):
  listed   = number of rows under "Assets" in runs/<version>__v1/gpt-5.6-luna__high/r<k>/assets/<module>.json
  names    = Counter of each row's "Asset RTL" (exact string, no normalisation)
  correct  = walk the reference rows (data/ground_truth/manual_gt_neorv32.json -> modules -> module -> assets)
             in file order; a row whose "element" still has a copy in `names` consumes one copy and counts 1
  findable = reference rows whose "element" is a port, signal or field name in
             inputs/v1/heldout/<module>/closed_set.json (any entity; "port" / "signal" / "field" keys,
             not the "counterparts" cross-references)
  recall   = correct / findable      precision = correct / listed

Self-test: fixed values hand-read from the files before this script was written. If any fails, nothing is reported.
"""
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(r"E:\jobs\ff\test\Prepoison_subset")
LAB = PROJECT / "final" / "pio" / "lab"
GT = PROJECT / "data" / "ground_truth" / "manual_gt_neorv32.json"
MODEL_DIR = "gpt-5.6-luna__high"
VERSIONS = ("two_phase_v9i", "two_phase_v9i_orderB")
RUNS = ("r0", "r1", "r2")
MODULES = ("neorv32_cpu_frontend", "neorv32_slink", "neorv32_cpu_icc", "neorv32_cpu_counters",
           "neorv32_cpu_control", "neorv32_debug_dm", "neorv32_xbus")
OUT = Path(__file__).with_name("results.json")


def load(p: Path):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def closed_names(module: str) -> dict:
    """{name: kind} for every port, signal and field declared in the module's closed set."""
    cs = load(LAB / "inputs" / "v1" / "heldout" / module / "closed_set.json")
    out = {}

    def walk(o):
        if isinstance(o, dict):
            for kind in ("port", "signal", "field"):
                if kind in o and isinstance(o[kind], str):
                    out.setdefault(o[kind], kind)
            for k, v in o.items():
                if k == "counterparts":
                    continue
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(cs)
    return out


def reference_rows(gt: dict, module: str) -> list:
    return [r["element"] for r in gt["modules"][module]["assets"]]


def listed_names(version: str, run: str, module: str) -> list:
    d = load(LAB / "runs" / f"{version}__v1" / MODEL_DIR / run / "assets" / f"{module}.json")
    return [a["Asset RTL"] for a in d["Assets"]]


def score_module(ref: list, listed: list, closed: dict) -> dict:
    names = Counter(listed)
    correct, hits, misses = 0, [], []
    for el in ref:
        if names[el] > 0:
            names[el] -= 1
            correct += 1
            hits.append(el)
        else:
            misses.append(el)
    findable = sum(1 for el in ref if el in closed)
    not_findable = [el for el in ref if el not in closed]
    extras = [n for n in listed if n not in set(ref)]
    return {"correct": correct, "listed": len(listed), "findable": findable, "reference rows": len(ref),
            "hits": hits, "misses": misses, "not findable": not_findable, "extras": extras}


def ratio(a: int, b: int) -> float:
    return round(a / b, 3) if b else 0.0


def main() -> int:
    gt = load(GT)
    closed = {m: closed_names(m) for m in MODULES}
    ref = {m: reference_rows(gt, m) for m in MODULES}

    per = {}  # (version, run, module) -> dict
    for v in VERSIONS:
        for r in RUNS:
            for m in MODULES:
                per[(v, r, m)] = score_module(ref[m], listed_names(v, r, m), closed[m])

    # ---- self-test: values hand-read from the files before writing this script ----
    expect = {
        ("two_phase_v9i", "r0", "neorv32_slink"): (13, 18, 13),
        ("two_phase_v9i", "r0", "neorv32_cpu_frontend"): (1, 3, 3),
        ("two_phase_v9i", "r0", "neorv32_cpu_icc"): (3, 3, 5),
        ("two_phase_v9i_orderB", "r1", "neorv32_cpu_frontend"): (1, 3, 3),
        ("two_phase_v9i_orderB", "r2", "neorv32_xbus"): (9, 16, 9),
    }
    fails = []
    for key, (c, l, f) in expect.items():
        got = (per[key]["correct"], per[key]["listed"], per[key]["findable"])
        if got != (c, l, f):
            fails.append(f"{key}: expected correct/listed/findable {(c, l, f)}, got {got}")
    # hand-read: cpu_control has 11 reference rows and mem_sync_i is not in its closed set
    cc = per[("two_phase_v9i", "r0", "neorv32_cpu_control")]
    if not (cc["reference rows"] == 11 and cc["findable"] == 10 and cc["not findable"] == ["mem_sync_i"]):
        fails.append(f"cpu_control findable: expected 10 of 11 with mem_sync_i absent, got {cc['findable']} of "
                     f"{cc['reference rows']}, absent={cc['not findable']}")
    # hand-read: total reference rows 3+13+5+11+11+6+9 = 58, findable 57
    tot_ref = sum(len(ref[m]) for m in MODULES)
    tot_find = sum(per[("two_phase_v9i", "r0", m)]["findable"] for m in MODULES)
    if (tot_ref, tot_find) != (58, 57):
        fails.append(f"totals: expected 58 reference rows / 57 findable, got {tot_ref} / {tot_find}")
    if fails:
        print("SELF-TEST FAILED -- no figures reported")
        for x in fails:
            print("  ", x)
        return 1
    print("SELF-TEST PASS (5 hand-read module triples, cpu_control findable 10/11, totals 58/57)")
    print()

    # ---- figures ----
    results = {"spec": __doc__.strip().splitlines()[0], "self test": "pass", "modules": list(MODULES),
               "findable per module": {m: per[("two_phase_v9i", "r0", m)]["findable"] for m in MODULES},
               "reference rows per module": {m: len(ref[m]) for m in MODULES},
               "not findable": {m: per[("two_phase_v9i", "r0", m)]["not findable"] for m in MODULES
                                if per[("two_phase_v9i", "r0", m)]["not findable"]},
               "versions": {}}
    print("findable per module:", {m: results["findable per module"][m] for m in MODULES},
          "total", sum(results["findable per module"].values()))
    print("not findable:", results["not findable"])
    print()
    for v in VERSIONS:
        vres = {"runs": {}, "pooled": {}}
        pc = pl = pf = 0
        print(f"=== {v}")
        for r in RUNS:
            c = sum(per[(v, r, m)]["correct"] for m in MODULES)
            l = sum(per[(v, r, m)]["listed"] for m in MODULES)
            f = sum(per[(v, r, m)]["findable"] for m in MODULES)
            pc, pl, pf = pc + c, pl + l, pf + f
            row = {"correct": c, "listed": l, "findable": f, "recall": ratio(c, f), "precision": ratio(c, l),
                   "per module": {m: {k: per[(v, r, m)][k] for k in ("correct", "listed", "findable", "misses", "extras")}
                                  for m in MODULES}}
            vres["runs"][r] = row
            print(f"  {r}: correct {c}  listed {l}  findable {f}  recall {c}/{f} = {row['recall']}  "
                  f"precision {c}/{l} = {row['precision']}")
            print("      per module correct/listed/findable:",
                  {m: (per[(v, r, m)]["correct"], per[(v, r, m)]["listed"], per[(v, r, m)]["findable"]) for m in MODULES})
        vres["pooled"] = {"correct": pc, "listed": pl, "findable": pf, "recall": ratio(pc, pf), "precision": ratio(pc, pl)}
        print(f"  pooled r0-r2: correct {pc}  listed {pl}  findable {pf}  recall {pc}/{pf} = {ratio(pc, pf)}  "
              f"precision {pc}/{pl} = {ratio(pc, pl)}")
        print()
        results["versions"][v] = vres

    # ---- per module per run correct, compact table ----
    print("per module per run: correct (listed)")
    hdr = "module".ljust(22) + "".join(f"{v[10:] or 'v9i':>12}{r:<4}" for v in VERSIONS for r in RUNS)
    print(hdr)
    for m in MODULES:
        cells = "".join(f"{per[(v, r, m)]['correct']:>12} ({per[(v, r, m)]['listed']:>2})" for v in VERSIONS for r in RUNS)
        print(m.ljust(22) + cells)
    print()

    # ---- diagnostics only (not figures): names that would match under a looser rule ----
    loose = []
    for (v, r, m), d in per.items():
        refset = set(ref[m])
        for n in d["extras"]:
            if n.strip().lower() in {x.lower() for x in refset} and n not in refset:
                loose.append((v, r, m, n))
    dup_listed = [(v, r, m, n, c) for (v, r, m), d in per.items()
                  for n, c in Counter(listed_names(v, r, m)).items() if c > 1]
    unknown = [(v, r, m, n) for (v, r, m), d in per.items() for n in d["extras"] if n not in closed[m]]
    print("diagnostics: listed names equal to a reference element only after strip/lower:", loose or "none")
    print("diagnostics: duplicate listed names within one module/run:", dup_listed or "none")
    print("diagnostics: listed names not in the module's closed set:", unknown or "none")
    results["diagnostics"] = {"loose matches": loose, "duplicate listed": dup_listed, "listed not in closed set": unknown}

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print("\nwrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
