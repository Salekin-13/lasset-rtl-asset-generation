"""Independent exact re-score of the v9g / v9h / v9i / v9j runs.

Scorer (as specified by the task, nothing else):
  listed   = number of rows under "Assets" in runs/<version>__v1/gpt-5.6-luna__high/r<k>/assets/<module>.json
  names    = Counter of those rows' "Asset RTL" strings (exact, case-sensitive)
  correct  = walk the reference rows (data/ground_truth/manual_gt_neorv32.json: modules -> module -> assets) in order;
             a row whose "element" still has a copy in the Counter consumes one copy and counts as correct
  findable = reference rows whose "element" is a port, signal or record-field name anywhere in the module's closed set
             (inputs/v1/<split>/<module>/closed_set.json, all entities)
  recall   = correct / findable      precision = correct / listed

The self-test at the top compares the scorer with hand-read values (see SELFTEST) and with the stored findable
denominators in splits/tuning_v2.json. If the self-test fails the script stops and reports nothing.

No lab code is imported; no API call is made.  Run with:  python -B score.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]                       # experiments/03_two_phase_csa_pio/lab
ROOT = LAB.parents[2]                       # project folder
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
INPUTS = LAB / "inputs" / "v1"
RUNS = LAB / "runs"
SPLIT = LAB / "splits" / "tuning_v2.json"
MODEL = "gpt-5.6-luna__high"

# version -> runs to score (v9g r1/r2: only the modules that have an assets file; flagged as partial)
PLAN = {
    "two_phase_v9j": ["r0", "r1", "r2"],
    "two_phase_v9i": ["r0"],
    "two_phase_v9h": ["r0", "r1"],
    "two_phase_v9g": ["r0", "r1", "r2"],
}

CONTROL = "neorv32_cpu_control"
WATCH = ["ctrl_o", "irq_machine_i", "irq_fast_i", "lsu_err_i", "debug_ctrl.run", "hwtrig_start",
         "csr.mepc", "csr.prv_level"]

# ---------------------------------------------------------------------------------------------- inputs ---


def gt_rows() -> dict[str, list[str]]:
    g = json.loads(GT.read_text(encoding="utf-8"))["modules"]
    return {m: [r["element"] for r in v["assets"]] for m, v in g.items()}


def module_dir(m: str) -> Path:
    for split in ("tuning", "heldout"):
        d = INPUTS / split / m
        if d.is_dir():
            return d
    raise FileNotFoundError(m)


def closed_set_names(m: str) -> set[str]:
    """Every port, signal and record-field name in the module's closed set, over all entities."""
    cs = json.loads((module_dir(m) / "closed_set.json").read_text(encoding="utf-8"))
    names: set[str] = set()
    for e in cs["entity list"]:
        for p in e.get("port list", []):
            names.add(p["port"])
            for f in p.get("fields") or []:
                names.add(f["field"])
        for s in e.get("signal list", []):
            names.add(s["signal"])
            for f in s.get("fields") or []:
                names.add(f["field"])
    return names


def assets_file(version: str, rep: str, m: str) -> Path:
    return RUNS / f"{version}__v1" / MODEL / rep / "assets" / f"{m}.json"


def listed_names(version: str, rep: str, m: str) -> list[str] | None:
    f = assets_file(version, rep, m)
    if not f.exists():
        return None
    return [x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]]


# ---------------------------------------------------------------------------------------------- scorer ---


def score_module(listed: list[str], ref: list[str], closed: set[str]) -> dict:
    pool = Counter(listed)
    correct = dup_hits = 0
    hit = []
    seen = Counter()
    for el in ref:                       # reference rows walked in order
        if pool[el] > 0:
            pool[el] -= 1
            correct += 1
            hit.append(el)
            if seen[el]:                 # a second copy of a repeated reference name counted correct
                dup_hits += 1
        seen[el] += 1
    findable = sum(1 for el in ref if el in closed)
    return {"correct": correct, "listed": len(listed), "findable": findable, "ref rows": len(ref), "hit": hit,
            "dup hits": dup_hits}


def groups() -> dict[str, list[str]]:
    gt = gt_rows()
    tuning15 = sorted(d.name for d in (INPUTS / "tuning").iterdir() if d.is_dir() and d.name in gt)
    heldout26 = sorted(d.name for d in (INPUTS / "heldout").iterdir() if d.is_dir())
    sp = json.loads(SPLIT.read_text(encoding="utf-8"))
    return {"tuning 15": tuning15, "held-out 26": heldout26,
            "tuning_v2": list(sp["tuning"]), "heldout_v2": list(sp["heldout"])}


def ratio(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


# ---------------------------------------------------------------------------------------------- self-test ---

SELFTEST = [
    # (version, rep, module, correct, listed, findable) -- hand-read from the files before the script was written.
    # cpu_control: 11 reference rows; mem_sync_i has no occurrence in the module's closed set or rtl.txt (grep: 0
    # hits in both, checked 2026-10-18), so findable is 10.
    ("two_phase_v9j", "r0", "neorv32_wdt", 7, 9, 8),
    ("two_phase_v9j", "r0", CONTROL, 9, 37, 10),
    ("two_phase_v9j", "r1", CONTROL, 10, 18, 10),
    ("two_phase_v9j", "r2", CONTROL, 10, 28, 10),
]
# Stored findable-per-run denominators in splits/tuning_v2.json (built 2026-10-14 by the project's own code).
# The project's loader (src/eval_assets.load_refs) caps a repeated reference name by the number of entities that
# declare it: neorv32_twi lists twi_sda_i and twi_sda_o in two rows each but one entity declares them, so it drops
# one row of each (2 rows). This scorer walks every reference row, as the task defines, so its tuning denominators
# are the stored ones + 2. The held-out groups contain no such row and must match exactly.
STORED_FINDABLE = {"tuning 15": 109, "held-out 26": 187, "tuning_v2": 206, "heldout_v2": 90}
TWI_DUP_ROWS = 2
EXPECTED_FINDABLE = {"tuning 15": 109 + TWI_DUP_ROWS, "held-out 26": 187, "tuning_v2": 206 + TWI_DUP_ROWS,
                     "heldout_v2": 90}


def duplicate_rows(ref: list[str]) -> list[str]:
    """Reference elements seen a second (or later) time, in walk order."""
    seen, out = Counter(), []
    for el in ref:
        if seen[el]:
            out.append(el)
        seen[el] += 1
    return out


def self_test(gt, grp) -> list[str]:
    bad = []
    for version, rep, m, c, l, f in SELFTEST:
        s = score_module(listed_names(version, rep, m), gt[m], closed_set_names(m))
        got = (s["correct"], s["listed"], s["findable"])
        if got != (c, l, f):
            bad.append(f"{version} {rep} {m}: expected (correct, listed, findable)={(c, l, f)}, got {got}")
    cc = closed_set_names(CONTROL)
    missing = [el for el in gt[CONTROL] if el not in cc]
    if missing != ["mem_sync_i"]:
        bad.append(f"{CONTROL}: reference elements not in the closed set: {missing} (expected only mem_sync_i)")
    # the only duplicate reference rows in the 41 modules that the project's loader would drop are twi's two
    twi_dups = duplicate_rows(gt["neorv32_twi"])
    if sorted(twi_dups) != ["twi_sda_i", "twi_sda_o"]:
        bad.append(f"neorv32_twi duplicate rows: {twi_dups}")
    for name, mods in grp.items():
        f = sum(score_module([], gt[m], closed_set_names(m))["findable"] for m in mods)
        if f != EXPECTED_FINDABLE[name]:
            bad.append(f"findable {name}: mine {f} vs expected {EXPECTED_FINDABLE[name]} "
                       f"(stored {STORED_FINDABLE[name]})")
    sizes = {k: len(v) for k, v in grp.items()}
    if sizes != {"tuning 15": 15, "held-out 26": 26, "tuning_v2": 27, "heldout_v2": 14}:
        bad.append(f"group sizes {sizes}")
    return bad


# ---------------------------------------------------------------------------------------------- main ---


def main() -> int:
    gt = gt_rows()
    grp = groups()
    problems = self_test(gt, grp)
    if problems:
        print("SELF-TEST FAILED; nothing reported")
        for p in problems:
            print("  ", p)
        return 1
    print("self-test passed:", len(SELFTEST), "hand-read module scores, 4 stored findable denominators, group sizes")
    print("groups:", {k: len(v) for k, v in grp.items()})

    closed = {m: closed_set_names(m) for mods in grp.values() for m in mods}
    report: dict = {"scorer": __doc__.strip().splitlines()[0], "groups": {k: v for k, v in grp.items()},
                    "per group": {}, "control unit": {}, "v9j watch names": {}, "partial runs": []}

    # per module scores, once per (version, rep, module)
    cache: dict[tuple[str, str, str], dict | None] = {}

    def sm(version, rep, m):
        k = (version, rep, m)
        if k not in cache:
            ln = listed_names(version, rep, m)
            cache[k] = None if ln is None else score_module(ln, gt[m], closed[m])
        return cache[k]

    for gname, mods in grp.items():
        out = {}
        for version, reps in PLAN.items():
            per_run = {}
            pooled_all = Counter()
            pooled_complete = Counter()
            n_complete = 0
            for rep in reps:
                c = l = f = dh = 0
                covered = []
                for m in mods:
                    s = sm(version, rep, m)
                    if s is None:
                        continue
                    covered.append(m)
                    c, l, f, dh = c + s["correct"], l + s["listed"], f + s["findable"], dh + s["dup hits"]
                if not covered:
                    per_run[rep] = {"modules with assets": 0, "note": "no assets file for any module of this group"}
                    continue
                partial = len(covered) < len(mods)
                row = {"correct": c, "listed": l, "findable": f, "recall": ratio(c, f), "precision": ratio(c, l),
                       "modules with assets": f"{len(covered)} of {len(mods)}",
                       "correct rows from a repeated reference name": dh}
                if partial:
                    row["note"] = "partial run: only the modules with an assets file are scored; findable is theirs"
                    report["partial runs"].append(f"{gname} / {version} / {rep}: {len(covered)} of {len(mods)}")
                else:
                    pooled_complete.update({"correct": c, "listed": l, "findable": f})
                    n_complete += 1
                pooled_all.update({"correct": c, "listed": l, "findable": f})
                per_run[rep] = row
            pc = pooled_complete
            pooled = {"runs": n_complete, "correct": pc["correct"], "listed": pc["listed"], "findable": pc["findable"],
                      "recall": ratio(pc["correct"], pc["findable"]), "precision": ratio(pc["correct"], pc["listed"])}
            entry = {"per run": per_run, "pooled (complete runs)": pooled}
            if pooled_all != pooled_complete:
                pa = pooled_all
                entry["pooled (all scored runs, partial included)"] = {
                    "correct": pa["correct"], "listed": pa["listed"], "findable": pa["findable"],
                    "recall": ratio(pa["correct"], pa["findable"]), "precision": ratio(pa["correct"], pa["listed"])}
            out[version] = entry
        report["per group"][gname] = out

    # control unit per version and run
    for version, reps in PLAN.items():
        for rep in reps:
            s = sm(version, rep, CONTROL)
            if s is None:
                report["control unit"][f"{version} {rep}"] = "no assets file"
            else:
                report["control unit"][f"{version} {rep}"] = {
                    "correct": s["correct"], "listed": s["listed"], "findable": s["findable"],
                    "reference rows hit": s["hit"],
                    "reference rows missed": [el for el in gt[CONTROL] if el not in s["hit"]]}

    # the eight watched names, per v9j run
    cc = closed[CONTROL]
    for rep in PLAN["two_phase_v9j"]:
        ln = listed_names("two_phase_v9j", rep, CONTROL) or []
        cnt = Counter(ln)
        report["v9j watch names"][rep] = {n: ("listed" if cnt[n] else "not listed") + (f" x{cnt[n]}" if cnt[n] > 1 else "")
                                          for n in WATCH}
    report["watch names context"] = {n: {"in reference": n in gt[CONTROL], "in closed set": n in cc} for n in WATCH}

    (HERE / "result.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

    # ---- plain-text tables
    print()
    for gname, out in report["per group"].items():
        print(f"=== {gname} ({len(grp[gname])} modules)")
        print(f"{'version':16} {'run':8} {'correct':>8} {'listed':>7} {'findable':>9} {'recall':>7} {'precision':>10}  note")
        for version, entry in out.items():
            for rep, row in entry["per run"].items():
                if "correct" not in row:
                    print(f"{version:16} {rep:8} {'-':>8} {'-':>7} {'-':>9} {'-':>7} {'-':>10}  {row['note']}")
                    continue
                print(f"{version:16} {rep:8} {row['correct']:8d} {row['listed']:7d} {row['findable']:9d} "
                      f"{row['recall']:7.3f} {row['precision']:10.3f}  {row.get('note', '')} "
                      f"[{row['modules with assets']}; dup-name hits {row['correct rows from a repeated reference name']}]")
            p = entry["pooled (complete runs)"]
            if p["runs"]:
                print(f"{version:16} {'pooled':8} {p['correct']:8d} {p['listed']:7d} {p['findable']:9d} "
                      f"{p['recall']:7.3f} {p['precision']:10.3f}  over {p['runs']} complete run(s)")
            q = entry.get("pooled (all scored runs, partial included)")
            if q:
                print(f"{version:16} {'pooled*':8} {q['correct']:8d} {q['listed']:7d} {q['findable']:9d} "
                      f"{q['recall']:7.3f} {q['precision']:10.3f}  * all scored runs, partial included")
        print()
    print("=== control unit (neorv32_cpu_control), findable", closed and sum(1 for el in gt[CONTROL] if el in cc))
    for k, v in report["control unit"].items():
        if isinstance(v, str):
            print(f"{k:22} {v}")
        else:
            print(f"{k:22} correct {v['correct']:2d}  listed {v['listed']:2d}  missed {v['reference rows missed']}")
    print()
    print("=== v9j: the eight watched names in cpu_control")
    for rep, d in report["v9j watch names"].items():
        print(rep, d)
    print("context:", report["watch names context"])
    if report["partial runs"]:
        print()
        print("partial runs:", *report["partial runs"], sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
