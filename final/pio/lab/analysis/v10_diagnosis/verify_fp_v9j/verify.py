"""Independent re-derivation of three readings on the stored two_phase_v9j output (gpt-5.6-luna, high, r0-r2).

Uses only chain.closed_names(m) and chain.run_dir from the lab. No API calls.

  python -B verify.py                 # self-test, then the three readings
  python -B verify.py dump <m> <k>    # one module/run in full, for a hand check
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
import chain  # noqa: E402

VERSION, MODEL, EFFORT, RUNS = "two_phase_v9j", "gpt-5.6-luna", "high", (0, 1, 2)
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
ASSIGN_KEYS = ("gets value from", "decided by", "reset by", "clocked by")


# ------------------------------------------------------------------------------------------- loading ---
def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def modules():
    """(all 41, held-out 26, tuning_v2 27, skipped). All = tuning + heldout folders with a reference entry."""
    gt = load(GT)["modules"]
    tun = sorted(p.name for p in (LAB / "inputs" / "v1" / "tuning").iterdir() if p.is_dir())
    held = sorted(p.name for p in (LAB / "inputs" / "v1" / "heldout").iterdir() if p.is_dir())
    allm = [m for m in tun + held if m in gt]
    skipped = [m for m in tun + held if m not in gt]
    # splits/tuning_v2.json has no "tuning_v2" key; its 27-module list is under "tuning" (interpretation).
    sp = load(LAB / "splits" / "tuning_v2.json")
    t2 = sp.get("tuning_v2") or sp["tuning"]
    assert all(m in allm for m in held), "a held-out folder has no reference entry"
    assert all(m in allm for m in t2), "a tuning_v2 module is not among the 41"
    return allm, held, t2, skipped


_CN: dict = {}


def closed(m: str) -> dict:
    if m not in _CN:
        _CN[m] = chain.closed_names(m)
    return _CN[m]


def closed_name_set(m: str) -> set:
    return {n for _, n in closed(m)}


def entry(m: str, entity, name: str):
    """The closed-set entry of a name: the row's entity first, else any entity carrying that name."""
    cn = closed(m)
    if entity is not None and (entity, name) in cn:
        return cn[(entity, name)]
    for (e, n), v in cn.items():
        if n == name:
            return v
    return None


def ref_rows(m: str) -> list:
    """Reference elements of module m, in file order, kept only when the element is a closed-set name."""
    rows = load(GT)["modules"][m]["assets"]
    names = closed_name_set(m)
    return [r["element"] for r in rows if r["element"] in names]


def listed_rows(m: str, k: int) -> list:
    d = chain.run_dir(VERSION, MODEL, k, EFFORT)
    return load(d / "assets" / f"{m}.json")["Assets"]


def phase1_concepts(m: str, k: int) -> dict:
    d = chain.run_dir(VERSION, MODEL, k, EFFORT)
    r = load(d / "phase1" / f"{m}.json")
    cs = (r.get("reply") or {}).get("conceptual assets") or []
    return {c.get("id"): c for c in cs if isinstance(c, dict)}


# ------------------------------------------------------------------------------------------- scoring ---
def score(names: list, ref: list):
    """Exact scorer. Returns (correct, leftover Counter = FP names with multiplicity, per-row correct flags).
    Correctness goes to the first copies of a name in list order."""
    cnt = Counter(names)
    consumed = Counter()
    for e in ref:
        if cnt[e] > 0:
            cnt[e] -= 1
            consumed[e] += 1
    flags = []
    seen = Counter()
    for n in names:
        seen[n] += 1
        flags.append(seen[n] <= consumed[n])
    correct = sum(consumed.values())
    assert correct == sum(flags)
    return correct, +cnt, flags


# ------------------------------------------------------------------------------------------ anchoring ---
def assignment_lines(m: str, entity, name: str) -> set:
    e = entry(m, entity, name)
    if not e:
        return set()
    out = set()
    for key in ASSIGN_KEYS:
        for c in (e.get("counterparts") or {}).get(key, []) or []:
            out.update(int(x) for x in c.get("lines", []) or [])
    return out


def _ints(xs) -> set:
    out = set()
    for x in xs or []:
        if isinstance(x, bool):
            continue
        if isinstance(x, (int, float)):
            out.add(int(x))
        elif isinstance(x, str) and x.strip().isdigit():
            out.add(int(x.strip()))
    return out


def anchored(m: str, row: dict, concepts: dict) -> bool:
    name = row["Asset RTL"]
    lines = assignment_lines(m, row.get("Entity"), name)
    for cid in row.get("Concepts") or []:
        c = concepts.get(cid)
        if not c:
            continue
        if name in (c.get("enters through") or []) or name in (c.get("leaves through") or []):
            return True
        if lines & _ints(c.get("held lines")):
            return True
    return False


def is_internal(m: str, row: dict) -> bool:
    """The top-level element (before the first '.') has no 'direction' key, i.e. is not a port."""
    top = row["Asset RTL"].split(".", 1)[0]
    e = entry(m, row.get("Entity"), top)
    return not (e is not None and "direction" in e)


# ------------------------------------------------------------------------------------------- spared ---
def spared_set():
    out = set()

    def fix(s: str) -> str:
        return s if s.startswith("neorv32_") else "neorv32_" + s
    for rule, me in load(LAB / "analysis" / "v10_diagnosis" / "v9g_targets.json"):
        out.add(fix(me))
    found_keys = Counter()
    for f in ("meta_v9h_shapes.json", "meta_v9i.json", "meta_v9k.json", "meta_v9k2.json"):
        d = load(LAB / "analysis" / "v10_diagnosis" / "new_rules" / f)

        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if k in ("intended_cases", "must_spare", "targets") and isinstance(v, list):
                        found_keys[k] += 1
                        for s in v:
                            if isinstance(s, str):
                                out.add(fix(s.split(" ")[0]))
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(d)
    for n in ("ctrl_o", "irq_machine_i", "irq_fast_i", "irq_dbg_i", "lsu_err_i", "pmp_fault_i", "lsu_wait_i",
              "alu_cp_done_i", "debug_ctrl.run", "hwtrig_start"):
        out.add(f"neorv32_cpu_control:{n}")
    return out, found_keys


# ------------------------------------------------------------------------------------------ self-test ---
# Hand-read from runs/two_phase_v9j__v1/gpt-5.6-luna__high/r0/assets/neorv32_spi.json, phase1/neorv32_spi.json,
# data/ground_truth/manual_gt_neorv32.json (neorv32_spi) and inputs/v1/tuning/neorv32_spi/closed_set.json.
SPI_R0 = {}   # filled in by hand after `dump neorv32_spi 0` was read (see HAND_CHECK below)


def selftest() -> None:
    c, left, flags = score(["a", "b", "a", "c"], ["a", "c", "d"])
    assert (c, dict(left), flags) == (2, {"a": 1, "b": 1}, [True, False, False, True]), (c, left, flags)
    if not HAND_CHECK:
        raise SystemExit("self-test has no hand-read values yet; run `dump neorv32_spi 0` and fill HAND_CHECK")
    names = [r["Asset RTL"] for r in listed_rows("neorv32_spi", 0)]
    ref = ref_rows("neorv32_spi")
    assert names == HAND_CHECK["listed"], names
    assert ref == HAND_CHECK["ref"], ref
    c, left, _ = score(names, ref)
    assert (c, dict(left)) == (HAND_CHECK["correct"], HAND_CHECK["fp"]), (c, left)
    assert assignment_lines("neorv32_spi", "neorv32_spi", "ctrl.cdiv") == {144, 139, 138, 137, 130, 118}
    concepts = phase1_concepts("neorv32_spi", 0)
    for r in listed_rows("neorv32_spi", 0):
        assert anchored("neorv32_spi", r, concepts) == HAND_CHECK["anchored"][r["Asset RTL"]], r["Asset RTL"]
        assert is_internal("neorv32_spi", r) == HAND_CHECK["internal"][r["Asset RTL"]], r["Asset RTL"]
    print("selftest PASS")


# ------------------------------------------------------------------------------------------ readings ---
def main() -> None:
    allm, held, t2, skipped = modules()
    print(f"modules: {len(allm)} (skipped, no reference entry: {skipped}); held-out {len(held)}; tuning_v2 {len(t2)}")
    multi = [m for m in allm if len({e for e, _ in closed(m)}) > 1]
    print(f"modules whose closed set has more than one entity: {multi}")
    spared, found = spared_set()
    print(f"spared set: {len(spared)} module:element strings; list keys found in meta files: {dict(found)}")

    data = {}   # (m, k) -> list of dict(name, correct, anchored, internal, spared)
    fp_total = listed_total = correct_total = 0
    fp_runs = Counter()   # (m, name) -> number of runs in which it is an FP
    anc = Counter()
    for m in allm:
        ref = ref_rows(m)
        for k in RUNS:
            rows = listed_rows(m, k)
            names = [r["Asset RTL"] for r in rows]
            c, left, flags = score(names, ref)
            fp_total += len(names) - c
            listed_total += len(names)
            correct_total += c
            assert sum(left.values()) == len(names) - c
            for n in left:
                fp_runs[(m, n)] += 1
            concepts = phase1_concepts(m, k)
            recs = []
            for r, ok in zip(rows, flags):
                a = anchored(m, r, concepts)
                recs.append({"name": r["Asset RTL"], "correct": ok, "anchored": a,
                             "internal": is_internal(m, r), "spared": f"{m}:{r['Asset RTL']}" in spared})
                anc[("anchored" if a else "not anchored", "correct" if ok else "FP")] += 1
            data[(m, k)] = recs

    print(f"\n(1) over 41 modules x 3 runs: listed {listed_total}, correct {correct_total}, FP occurrences {fp_total}")
    by = Counter(fp_runs.values())
    print(f"    distinct (module, name) FP pairs in 3 / 2 / 1 runs: {by[3]} / {by[2]} / {by[1]}  "
          f"(distinct pairs total {len(fp_runs)})")

    print("\n(2) anchored rows:     correct", anc[("anchored", "correct")], "FP", anc[("anchored", "FP")])
    print("    not anchored rows: correct", anc[("not anchored", "correct")], "FP", anc[("not anchored", "FP")])

    print("\n(3) post-filter V3 (drop not-anchored internal rows unless spared), pooled over 3 runs")
    for label, group in (("held-out 26", held), ("tuning_v2", t2)):
        c0 = l0 = c1 = l1 = 0
        dropped_correct = []
        dropped = 0
        for m in group:
            ref = ref_rows(m)
            for k in RUNS:
                recs = data[(m, k)]
                drop = [not r["anchored"] and r["internal"] and not r["spared"] for r in recs]
                keep = [r for r, d in zip(recs, drop) if not d]
                dropped += sum(drop)
                dropped_correct += [f"{m}:{r['name']} (r{k})" for r, d in zip(recs, drop) if d and r["correct"]]
                c0 += sum(r["correct"] for r in recs)
                l0 += len(recs)
                c, _, _ = score([r["name"] for r in keep], ref)
                c1 += c
                l1 += len(keep)
        print(f"  {label} ({len(group)} modules): no filter correct {c0} / listed {l0};  "
              f"V3 correct {c1} / listed {l1};  rows dropped {dropped}")
        print(f"    correct rows dropped ({len(dropped_correct)}):")
        for s in dropped_correct:
            print("      " + s)


def dump(m: str, k: int) -> None:
    ref = ref_rows(m)
    rows = listed_rows(m, k)
    names = [r["Asset RTL"] for r in rows]
    c, left, flags = score(names, ref)
    concepts = phase1_concepts(m, k)
    print("reference (closed-set names, file order):", ref)
    print("listed:", names)
    print("correct", c, "FP", dict(left))
    for r, ok in zip(rows, flags):
        print(f"  {r['Asset RTL']:30s} correct={ok!s:5} anchored={anchored(m, r, concepts)!s:5} "
              f"internal={is_internal(m, r)!s:5} concepts={r.get('Concepts')} "
              f"assign_lines={sorted(assignment_lines(m, r.get('Entity'), r['Asset RTL']))}")
    for cid, cc in concepts.items():
        print(f"  {cid}: enters={cc.get('enters through')} leaves={cc.get('leaves through')} "
              f"held={cc.get('held lines')}")


# Hand-read on 2026-10-18 from the raw files (grep of the assets file, the reference segment, the Phase 1 reply and the
# closed set), independently of the functions above.
HAND_CHECK = {
    "listed": ["rtx_engine.sreg", "spi_dat_o", "spi_dat_i", "ctrl.enable", "clkgen_en_o", "ctrl.prsc", "ctrl.cdiv",
               "ctrl.highspeed", "rtx_engine.cs_ctrl", "spi_csn_o", "irq_o"],
    "ref": ["ctrl.enable", "ctrl.cdiv", "ctrl.prsc", "spi_csn_o", "clkgen_en_o", "spi_dat_o", "spi_dat_i", "irq_o"],
    "correct": 8,
    "fp": {"rtx_engine.sreg": 1, "ctrl.highspeed": 1, "rtx_engine.cs_ctrl": 1},
    # C1 enters bus_req_i.data leaves spi_dat_o held []; C2 enters spi_dat_i leaves bus_rsp_o.data held [];
    # C3 leaves bus_rsp_o.data, clkgen_en_o held [140]; C4 held [143,144,145]; C5 leaves spi_csn_o held [290];
    # C6 leaves irq_o held [255]. ctrl.enable gets its value at 140, ctrl.prsc 143, ctrl.cdiv 144, ctrl.highspeed 145,
    # rtx_engine.cs_ctrl 290 (closed set "gets value from").
    "anchored": {"rtx_engine.sreg": False, "spi_dat_o": True, "spi_dat_i": True, "ctrl.enable": True,
                 "clkgen_en_o": True, "ctrl.prsc": True, "ctrl.cdiv": True, "ctrl.highspeed": True,
                 "rtx_engine.cs_ctrl": True, "spi_csn_o": True, "irq_o": True},
    # ports of neorv32_spi: clk_i rstn_i bus_req_i bus_rsp_o clkgen_en_o clkgen_i spi_clk_o spi_dat_o spi_dat_i
    # spi_csn_o irq_o; ctrl and rtx_engine are signals.
    "internal": {"rtx_engine.sreg": True, "spi_dat_o": False, "spi_dat_i": False, "ctrl.enable": True,
                 "clkgen_en_o": False, "ctrl.prsc": True, "ctrl.cdiv": True, "ctrl.highspeed": True,
                 "rtx_engine.cs_ctrl": True, "spi_csn_o": False, "irq_o": False},
}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "dump":
        dump(sys.argv[2], int(sys.argv[3]))
    else:
        selftest()
        main()
