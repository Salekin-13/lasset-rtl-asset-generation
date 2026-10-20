"""Independent exact re-scorer for two_phase_v9h / two_phase_v9g on the seven cell modules.

Reads only: the reference JSON, each run's assets/<module>.json, and each module's closed_set.json.
Imports nothing from the lab. No API calls.

Exact scorer (as specified by the task):
  per module, Counter of listed names ("Asset RTL" of every row under "Assets");
  walk the reference rows in order; a row whose element still has a listed copy consumes one and counts correct.
  listed   = number of asset rows
  findable = reference rows whose element is a port, signal or field name in the module's closed set
  all_rows = every reference row
"""
import json
from collections import Counter
from pathlib import Path

PROJ = Path(r"E:\jobs\ff\test\Prepoison_subset")
LAB = PROJ / "experiments" / "03_two_phase_csa_pio" / "lab"
GT_PATH = PROJ / "data" / "ground_truth" / "manual_gt_neorv32.json"
MODEL = "gpt-5.6-luna__high"
MODULES = ["neorv32_cpu_frontend", "neorv32_slink", "neorv32_cpu_icc", "neorv32_cpu_counters",
           "neorv32_cpu_control", "neorv32_debug_dm", "neorv32_xbus"]
VERSIONS = ["two_phase_v9h", "two_phase_v9g"]
RUNS = ["r0", "r1", "r2"]

REF_CHECKS = [  # (module, reference element) -> is it found (counted correct) in each version/run
    ("neorv32_cpu_control", "alu_cp_done_i"), ("neorv32_cpu_control", "lsu_wait_i"),
    ("neorv32_xbus", "xbus_ack_i"), ("neorv32_xbus", "xbus_err_i"),
    ("neorv32_slink", "slink_rx_valid_i"), ("neorv32_slink", "slink_tx_ready_i"),
    ("neorv32_slink", "slink_rx_ready_o"), ("neorv32_slink", "slink_tx_valid_o"),
    ("neorv32_debug_dm", "dm_ctrl.busy"), ("neorv32_cpu_counters", "inc_i"),
    ("neorv32_cpu_frontend", "ipb.free"), ("neorv32_cpu_frontend", "ipb.avail"),
    ("neorv32_cpu_icc", "tx_fifo_we"), ("neorv32_cpu_icc", "tx_fifo_free"),
    ("neorv32_slink", "slink_tx_data_o"), ("neorv32_slink", "slink_tx_last_o"),
]
NONREF_CHECKS = [  # (module, non-reference name) -> is it listed in each version/run
    ("neorv32_slink", "rx_fifo.we"), ("neorv32_slink", "tx_fifo.re"), ("neorv32_slink", "tx_fifo.avail"),
    ("neorv32_slink", "rx_fifo.free"), ("neorv32_cpu_frontend", "ipb.we"), ("neorv32_cpu_frontend", "ipb.re"),
    ("neorv32_debug_dm", "dm_ctrl.state"), ("neorv32_cpu_counters", "cnt_acc"), ("neorv32_cpu_counters", "cfg_acc"),
]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def closed_names(m: str) -> set:
    """Every port, signal and (recursively) field name in the module's closed set, over all entities."""
    cs = load(LAB / "inputs" / "v1" / "heldout" / m / "closed_set.json")
    names = set()

    def add_fields(x):
        for f in x.get("fields", []) or []:
            names.add(f["field"])
            add_fields(f)

    for e in cs["entity list"]:
        for x in e.get("port list", []):
            names.add(x["port"])
            add_fields(x)
        for x in e.get("signal list", []):
            names.add(x["signal"])
            add_fields(x)
    return names


def ref_rows(gt: dict, m: str) -> list:
    return [r["element"] for r in gt["modules"][m]["assets"]]


def listed_names(version: str, run: str, m: str) -> list:
    p = LAB / "runs" / f"{version}__v1" / MODEL / run / "assets" / f"{m}.json"
    a = load(p)
    return [x["Asset RTL"] for x in a["Assets"]]


def exact_score(ref: list, listed: list, closed: set):
    """Returns (correct, listed, findable, all_rows, found_flags_per_ref_row)."""
    c = Counter(listed)
    found = []
    for e in ref:
        if c[e] > 0:
            c[e] -= 1
            found.append(True)
        else:
            found.append(False)
    findable = sum(1 for e in ref if e in closed)
    return sum(found), len(listed), findable, len(ref), found


def self_test():
    """Hand-built cases for the scorer; fails loudly if the logic is off."""
    # duplicate reference rows consume separate listed copies
    cor, lst, fnd, alln, fl = exact_score(["a", "a", "b", "c"], ["a", "b", "b", "zz"], {"a", "b"})
    assert (cor, lst, fnd, alln, fl) == (2, 4, 3, 4, [True, False, True, False]), (cor, lst, fnd, alln, fl)
    # case / whitespace are NOT normalised (exact)
    cor, *_ = exact_score(["A"], ["a"], set())
    assert cor == 0
    cor, *_ = exact_score(["a "], ["a"], set())
    assert cor == 0
    # empty listed
    assert exact_score(["a"], [], {"a"})[:4] == (0, 0, 1, 1)
    # hand check against a file read in the session: v9h r0 slink lists these four as its first four rows
    l = listed_names("two_phase_v9h", "r0", "neorv32_slink")
    assert l[:4] == ["slink_rx_valid_i", "slink_rx_ready_o", "slink_tx_ready_i", "slink_tx_valid_o"], l[:4]
    cn = closed_names("neorv32_slink")
    for n in ("clk_i", "rstn_i", "bus_req_i", "bus_req_i.addr", "ctrl", "ctrl.enable", "rx_fifo.we", "tx_fifo.re"):
        assert n in cn, n
    # hand check against the reference file read in the session: slink has 13 rows, first is ctrl.enable
    gt = load(GT_PATH)
    r = ref_rows(gt, "neorv32_slink")
    assert len(r) == 13 and r[0] == "ctrl.enable" and r[1] == "slink_rx_src_i", r[:2]
    return True


def main():
    assert self_test()
    gt = load(GT_PATH)
    figures = {"per_version_run": {}, "pooled": {}, "per_module_correct": {}, "ref_entry_found": {},
               "nonref_listed": {}, "module_sizes": {}}
    problems = []

    closed = {m: closed_names(m) for m in MODULES}
    refs = {m: ref_rows(gt, m) for m in MODULES}
    for m in MODULES:
        r = refs[m]
        dups = sorted(k for k, v in Counter(r).items() if v > 1)
        if dups:
            problems.append(f"{m}: reference element listed more than once: {dups}")
        odd = [e for e in r if not isinstance(e, str) or e != e.strip()]
        if odd:
            problems.append(f"{m}: reference elements with stray whitespace / non-string: {odd}")
        not_closed = [e for e in r if e not in closed[m]]
        figures["module_sizes"][m] = {"ref_rows": len(r), "findable": len(r) - len(not_closed),
                                      "not_in_closed_set": not_closed}

    # which reference check entries exist in the reference, and which non-ref names really are non-reference
    for m, e in REF_CHECKS:
        if e not in refs[m]:
            problems.append(f"reference check {m} {e}: not a reference element")
        if e not in closed[m]:
            problems.append(f"reference check {m} {e}: not in the closed set (not findable)")
    for m, e in NONREF_CHECKS:
        if e in refs[m]:
            problems.append(f"non-reference check {m} {e}: IS a reference element")
        if e not in closed[m]:
            problems.append(f"non-reference check {m} {e}: not in the closed set")

    for v in VERSIONS:
        figures["per_version_run"][v] = {}
        figures["per_module_correct"][v] = {m: {} for m in MODULES}
        figures["ref_entry_found"][v] = {}
        figures["nonref_listed"][v] = {}
        pool = Counter()
        for run in RUNS:
            tot = Counter()
            found_map, listed_map = {}, {}
            for m in MODULES:
                lst = listed_names(v, run, m)
                cor, nl, fnd, alln, flags = exact_score(refs[m], lst, closed[m])
                tot.update({"correct": cor, "listed": nl, "findable": fnd, "all_rows": alln})
                figures["per_module_correct"][v][m][run] = cor
                found_map[m] = {e: f for e, f in zip(refs[m], flags)}  # if an element repeats, last row wins
                listed_map[m] = set(lst)
            rec_f = tot["correct"] / tot["findable"] if tot["findable"] else None
            rec_a = tot["correct"] / tot["all_rows"] if tot["all_rows"] else None
            prec = tot["correct"] / tot["listed"] if tot["listed"] else None
            figures["per_version_run"][v][run] = {
                "correct": tot["correct"], "listed": tot["listed"], "findable": tot["findable"],
                "all_rows": tot["all_rows"],
                "recall_findable": round(rec_f, 4) if rec_f is not None else None,
                "recall_all_rows": round(rec_a, 4) if rec_a is not None else None,
                "precision": round(prec, 4) if prec is not None else None,
            }
            pool.update(tot)
            figures["ref_entry_found"][v][run] = {f"{m} {e}": bool(found_map[m].get(e, False)) for m, e in REF_CHECKS}
            figures["nonref_listed"][v][run] = {f"{m} {e}": (e in listed_map[m]) for m, e in NONREF_CHECKS}
        figures["pooled"][v] = {
            "correct": pool["correct"], "listed": pool["listed"], "findable": pool["findable"],
            "all_rows": pool["all_rows"],
            "recall_findable": round(pool["correct"] / pool["findable"], 4),
            "recall_all_rows": round(pool["correct"] / pool["all_rows"], 4),
            "precision": round(pool["correct"] / pool["listed"], 4),
        }

    out = {"figures": figures, "problems": problems}
    (Path(__file__).parent / "figures.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
