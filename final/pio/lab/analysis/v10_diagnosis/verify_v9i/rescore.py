"""Independent exact re-scorer for two_phase_v9i r0 and two_phase_v9h r0/r1 on four module groups.

Own code only: reads the built inputs (closed_set.json), the reference JSON, the split file and the stored
assets/<module>.json files. Imports nothing from the lab. Sends nothing.

Scorer (exact, per module):
  listed   = number of rows under "Assets" (duplicates count)
  pool     = Counter of the "Asset RTL" names
  walk the reference rows in order; a row whose element still has a copy in the pool consumes one and is correct
  findable = reference rows whose element is a port, signal or field name in the module's closed set
  recall = correct / findable, precision = correct / listed  (pooled over the group's modules)

Run:  python -B rescore.py   (writes figures.json next to this file and prints a report)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
GT_PATH = Path(r"E:\jobs\ff\test\Prepoison_subset\data\ground_truth\manual_gt_neorv32.json")
SPLIT_PATH = LAB / "splits" / "tuning_v2.json"
MODEL = "gpt-5.6-luna__high"
TARGETS = [("two_phase_v9i", 0), ("two_phase_v9h", 0), ("two_phase_v9h", 1)]

NAMES_48 = """cache:data_mem_b0, cache:data_mem_b1, imem:mem_ram_b0, imem:mem_ram_b1, dmem:mem_ram_b0, dmem:mem_ram_b1,
dmem:rdata, imem:rdata, cpu_control:csr.mcause, cpu_control:csr.mepc, cpu_control:csr.prv_level,
cpu_control:csr.mstatus_mpp, cpu_control:exe_engine.pc, cpu_control:trap_ctrl.cause, cpu_control:debug_ctrl.run,
cpu_control:hwtrig_start, cpu_control:ctrl_o, cpu_control:irq_machine_i, debug_dtm:dmi_ctrl.addr, debug_dtm:dmi_ctrl.op,
debug_dtm:dmi_ctrl.wdata, debug_dtm:tap_reg.dmi, debug_dtm:tap_reg.dtmcs, debug_dtm:dmi_ctrl.busy, cpu_control:frontend_i,
cpu_frontend:frontend_o, cpu_icc:icc_rx_i, cpu_icc:icc_tx_o, cpu_frontend:ctrl_i, cpu_alu:ctrl_i, cpu_lsu:ctrl_i,
bus:arbiter.rdata, bus:int_rsp.err, bus:main_rsp.err, bus:sc_fail, xbus:bus_rsp.ack, xbus:bus_rsp.err, xbus:timeout,
gpio:port_in, gpio:irq_pend, cpu_regfile:reg_file, cpu_cp_cfu:key_mem, slink:slink_rx_valid_i, slink:slink_tx_ready_i,
cpu_control:alu_cp_done_i, debug_dm:dm_ctrl.busy, xbus:xbus_dat_i, xbus:xbus_dat_o"""
NAMES_48 = [x.strip() for x in NAMES_48.replace("\n", " ").split(",") if x.strip()]
assert len(NAMES_48) == 48, len(NAMES_48)


# ----------------------------------------------------------------------------------------------------------- inputs
def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def module_dir(module: str) -> Path:
    for split in ("tuning", "heldout"):
        d = LAB / "inputs" / "v1" / split / module
        if (d / "closed_set.json").exists():
            return d
    raise FileNotFoundError(module)


def closed_set_names(module: str) -> set[str]:
    """Port, signal and field names of every entity in the module's closed set (names only, entity dropped)."""
    cs = load_json(module_dir(module) / "closed_set.json")
    names: set[str] = set()
    for e in cs["entity list"]:
        for x in e.get("port list", []):
            names.add(x["port"])
            for f in x.get("fields", []):
                names.add(f["field"])
        for x in e.get("signal list", []):
            names.add(x["signal"])
            for f in x.get("fields", []):
                names.add(f["field"])
    return names


def listed_names(version: str, run: int, module: str) -> list[str] | None:
    p = LAB / "runs" / f"{version}__v1" / MODEL / f"r{run}" / "assets" / f"{module}.json"
    if not p.exists():
        return None
    return [a["Asset RTL"] for a in load_json(p)["Assets"]]


def reference_rows(gt: dict, module: str) -> list[str]:
    return [a["element"] for a in gt["modules"][module]["assets"]]


# ----------------------------------------------------------------------------------------------------------- scorer
def score_module(ref_elements: list[str], listed: list[str], closed: set[str]) -> dict:
    pool = Counter(listed)
    correct = 0
    correct_not_findable = 0
    findable = 0
    excluded = []
    matched = []
    for el in ref_elements:
        in_closed = el in closed
        if in_closed:
            findable += 1
        else:
            excluded.append(el)
        if pool[el] > 0:
            pool[el] -= 1
            correct += 1
            matched.append(el)
            if not in_closed:
                correct_not_findable += 1
    return {"correct": correct, "listed": len(listed), "findable": findable, "reference_rows": len(ref_elements),
            "excluded": excluded, "correct_not_findable": correct_not_findable, "matched": matched}


def self_test() -> None:
    """Hand-built case: duplicate reference rows, duplicate listed names, a reference element outside the closed set."""
    ref = ["a", "b", "b", "c", "z"]          # z is not in the closed set; b appears twice
    listed = ["a", "b", "x", "x", "z"]       # b listed once -> only the first b row is correct; z listed and matched
    closed = {"a", "b", "c", "x"}
    r = score_module(ref, listed, closed)
    assert r["correct"] == 3, r               # a, first b, z
    assert r["listed"] == 5, r
    assert r["findable"] == 4, r              # a, b, b, c
    assert r["excluded"] == ["z"], r
    assert r["correct_not_findable"] == 1, r  # z
    assert r["matched"] == ["a", "b", "z"], r
    # empty listing
    r = score_module(ref, [], closed)
    assert (r["correct"], r["listed"], r["findable"]) == (0, 0, 4), r


# ----------------------------------------------------------------------------------------------------------- groups
def groups(gt: dict) -> dict[str, list[str]]:
    tuning_dir = LAB / "inputs" / "v1" / "tuning"
    heldout_dir = LAB / "inputs" / "v1" / "heldout"
    tuning_all = sorted(d.name for d in tuning_dir.iterdir() if d.is_dir() and (d / "closed_set.json").exists())
    tuning15 = [m for m in tuning_all if m in gt["modules"] and gt["modules"][m]["assets"]]
    tuning_skipped = [m for m in tuning_all if m not in tuning15]
    heldout26 = sorted(d.name for d in heldout_dir.iterdir() if d.is_dir() and (d / "closed_set.json").exists())
    split = load_json(SPLIT_PATH)
    g = {"tuning_15": tuning15, "heldout_26": heldout26,
         "tuning_v2": list(split["tuning"]), "heldout_v2": list(split["heldout"])}
    return g, tuning_skipped


def main() -> None:
    self_test()
    gt = load_json(GT_PATH)
    g, tuning_skipped = groups(gt)
    for name, mods in g.items():
        for m in mods:
            assert m in gt["modules"] and gt["modules"][m]["assets"], (name, m)
    all_modules = sorted(set(sum(g.values(), [])))
    closed = {m: closed_set_names(m) for m in all_modules}
    ref = {m: reference_rows(gt, m) for m in all_modules}

    per_module: dict[str, dict[str, dict]] = {}   # "version:r<k>" -> module -> score
    missing_files = []
    for version, run in TARGETS:
        key = f"{version}:r{run}"
        per_module[key] = {}
        for m in all_modules:
            listed = listed_names(version, run, m)
            if listed is None:
                missing_files.append((key, m))
                listed = []
            per_module[key][m] = score_module(ref[m], listed, closed[m])

    # group figures
    group_figures: dict[str, dict] = {}
    for gname, mods in g.items():
        group_figures[gname] = {"modules": len(mods)}
        for key in per_module:
            c = sum(per_module[key][m]["correct"] for m in mods)
            l = sum(per_module[key][m]["listed"] for m in mods)
            f = sum(per_module[key][m]["findable"] for m in mods)
            rr = sum(per_module[key][m]["reference_rows"] for m in mods)
            cnf = sum(per_module[key][m]["correct_not_findable"] for m in mods)
            group_figures[gname][key] = {
                "correct": c, "listed": l, "findable": f, "reference_rows": rr,
                "recall": round(c / f, 4) if f else None, "precision": round(c / l, 4) if l else None,
                "correct_not_findable": cnf}

    # excluded reference rows (not in closed set) - same for every run
    excluded = {m: per_module[TARGETS[0][0] + f":r{TARGETS[0][1]}"][m]["excluded"] for m in all_modules
                if per_module[TARGETS[0][0] + f":r{TARGETS[0][1]}"][m]["excluded"]}
    excluded_by_group = {gname: sum(len(excluded.get(m, [])) for m in mods) for gname, mods in g.items()}

    # the 48 names
    names48: dict[str, dict] = {}
    for item in NAMES_48:
        short, el = item.split(":", 1)
        m = "neorv32_" + short
        row = {"in_reference": el in ref[m], "in_closed_set": el in closed[m]}
        for version, run in TARGETS:
            lst = listed_names(version, run, m) or []
            row[f"{version}:r{run}"] = el in lst
            row[f"{version}:r{run}_copies"] = lst.count(el)
        names48[item] = row

    out = {"targets": [f"{v}:r{r}" for v, r in TARGETS], "model_dir": MODEL,
           "groups": {k: v for k, v in g.items()}, "tuning_folders_skipped_no_reference": tuning_skipped,
           "group_figures": group_figures, "excluded_reference_rows": excluded,
           "excluded_count_by_group": excluded_by_group, "missing_asset_files": missing_files,
           "names_48": names48,
           "per_module": {key: {m: {kk: vv for kk, vv in s.items() if kk != "matched"} for m, s in d.items()}
                          for key, d in per_module.items()}}
    (HERE / "figures.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    # report
    print("self-test: pass")
    print("tuning folders skipped (no reference rows):", tuning_skipped)
    print("missing asset files:", missing_files)
    for gname, mods in g.items():
        print(f"\n== {gname} ({len(mods)} modules; excluded reference rows {excluded_by_group[gname]}) ==")
        for key in per_module:
            x = group_figures[gname][key]
            print(f"  {key:22s} correct {x['correct']:4d}  listed {x['listed']:4d}  findable {x['findable']:4d}  "
                  f"(ref rows {x['reference_rows']})  recall {x['recall']}  precision {x['precision']}  "
                  f"correct-not-findable {x['correct_not_findable']}")
    print("\n== excluded reference rows (element not a port/signal/field name in the closed set) ==")
    for m, els in sorted(excluded.items()):
        print(f"  {m}: {els}")
    print("\n== the 48 names (listed?) ==")
    hdr = "  ".join(f"{v.replace('two_phase_', '')}:r{r}" for v, r in TARGETS)
    print(f"  {'module:element':34s} ref  closed  {hdr}")
    for item, row in names48.items():
        flags = "  ".join(f"{str(row[f'{v}:r{r}']):6s}" for v, r in TARGETS)
        print(f"  {item:34s} {str(row['in_reference']):5s} {str(row['in_closed_set']):6s} {flags}")


if __name__ == "__main__":
    main()
