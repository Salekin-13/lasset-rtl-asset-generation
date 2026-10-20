"""Independent re-count of the Phase 1 LOCATED tier for five arms on the held-out 26 (gpt-5.6-luna, high, r0-r2).

Re-implements the LOCATED rule from its written description (no call into chain.located). Uses chain only for
chain.closed_names(module) and chain.run_dir(version, model, rep). Never sends an API call.

  python -B verify.py            -> prints the report and writes verify_tier1.json next to this file
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from math import comb
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (closed_names, run_dir only)

GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
HELDOUT = LAB / "inputs" / "v1" / "heldout"
MODEL, EFFORT = "gpt-5.6-luna", "high"
A = "two_phase_v9n_place"
ARMS = ["two_phase_v9n_place", "two_phase_p1o_first", "two_phase_v9n_place_dbg", "two_phase_p1o_last", "two_phase_p1o_sham"]
RUNS = (0, 1, 2)
DEBUG = "neorv32_debug_dm"
NINE = [("neorv32_xbus", "xbus_dat_i"), ("neorv32_xbus", "xbus_dat_o"), ("neorv32_xbus", "xbus_stb_o"),
        ("neorv32_xbus", "xbus_cyc_o"), ("neorv32_cpu_lsu", "err_o"), ("neorv32_debug_dm", "ndmrstn_o"),
        ("neorv32_gpio", "port_in"), ("neorv32_cpu_cp_cond", "ctrl_i"), ("neorv32_cpu_cp_shifter", "res_o")]


# ------------------------------------------------------------------------------------------------ inputs ---
def modules() -> list[str]:
    return sorted(p.name for p in HELDOUT.iterdir() if p.is_dir())


def reference(mods: list[str]) -> list[tuple[str, str, int]]:
    """(module, element, duplicate index) for every GT row whose element is a closed-set name of the module.
    Duplicates kept; the index counts repeats of (module, element) in row order."""
    gt = json.loads(GT.read_text(encoding="utf-8"))["modules"]
    out, seen = [], Counter()
    for m in mods:
        names = {x for (_, x) in chain.closed_names(m)}
        for row in gt[m]["assets"]:
            el = row.get("element")
            if el in names:
                out.append((m, el, seen[(m, el)]))
                seen[(m, el)] += 1
    return out


def assign_lines(m: str) -> dict[str, set[int]]:
    """name -> union over every entity carrying the name of the integer 'lines' of its counterparts under
    gets value from / decided by / reset by / clocked by."""
    out: dict[str, set[int]] = {}
    for (_, name), entry in chain.closed_names(m).items():
        ls = out.setdefault(name, set())
        cps = entry.get("counterparts") or {}
        for key in ("gets value from", "decided by", "reset by", "clocked by"):
            for c in cps.get(key) or []:
                if isinstance(c, dict):
                    ls.update(l for l in (c.get("lines") or []) if isinstance(l, int) and not isinstance(l, bool))
    return out


def _as_list(v):
    return v if isinstance(v, list) else ([v] if isinstance(v, str) else [])


def located_sets(m: str, concepts: list, names: set[str], assign: dict[str, set[int]]) -> dict[str, set[str]]:
    """Concept ID -> set of closed-set names it locates (Enters/Leaves names that are closed names, plus names with an
    assignment line among the Held Lines; integer lines only)."""
    out = {}
    for i, c in enumerate(concepts):
        if not isinstance(c, dict):
            continue
        cid = str(c.get("Concept ID") or f"#{i}")
        ports = [p for p in _as_list(c.get("Enters Through")) + _as_list(c.get("Leaves Through")) if isinstance(p, str)]
        held = {l for l in _as_list(c.get("Held Lines")) if isinstance(l, int) and not isinstance(l, bool)}
        out[cid] = {p for p in ports if p in names} | {x for x, ls in assign.items() if ls & held}
    return out


def phase1_concepts(arm: str, rep: int, m: str):
    """The 'Conceptual Assets' list of the raw Phase 1 reply, or None when the record is missing or unparseable."""
    f = chain.run_dir(arm, MODEL, rep, EFFORT) / "phase1" / f"{m}.json"
    if not f.exists():
        return None
    rec = json.loads(f.read_text(encoding="utf-8"))
    raw = rec.get("raw")
    if not isinstance(raw, str):
        return None
    try:
        j = json.loads(raw)
    except json.JSONDecodeError:
        return None
    ca = j.get("Conceptual Assets") if isinstance(j, dict) else None
    return ca if isinstance(ca, list) else None


# ------------------------------------------------------------------------------------------------ stats ---
def binom_two_sided(k: int, n: int) -> float | None:
    """Two-sided exact binomial p for k successes in n trials at p = 0.5 (sign test). None when n == 0."""
    if n == 0:
        return None
    pk = comb(n, k) / 2 ** n
    return min(1.0, sum(comb(n, i) for i in range(n + 1) if comb(n, i) / 2 ** n <= pk + 1e-12) / 2 ** n)


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest():
    """Hand-read: two_phase_v9n_place r0 neorv32_gpio concept C1 has Enters Through [gpio_i], Leaves Through
    [bus_rsp_o.data], Held Lines [100, 103]; in closed_set.json port_in 'gets value from' gpio_i at line 103, so the
    LOCATED set must be exactly {gpio_i, bus_rsp_o.data, port_in}. Also: an entry with no ports and no held lines
    locates nothing, and a non-closed-set port name is dropped."""
    m = "neorv32_gpio"
    names = {x for (_, x) in chain.closed_names(m)}
    assign = assign_lines(m)
    assert assign["port_in"] >= {103, 102, 99}, assign["port_in"]        # gets value from 103, clocked 102, reset 99
    ca = phase1_concepts(A, 0, m)
    c1 = [c for c in ca if c.get("Concept ID") == "C1"][0]
    assert c1["Enters Through"] == ["gpio_i"] and c1["Leaves Through"] == ["bus_rsp_o.data"] and c1["Held Lines"] == [100, 103], c1
    got = located_sets(m, [c1], names, assign)["C1"]
    # line 100 is the reset branch of the port_in process: is any closed name assigned there? compute what the rule says
    # and compare against the hand-read expectation plus whatever closed names carry 100 as an assignment line.
    extra100 = {x for x, ls in assign.items() if 100 in ls}
    assert got == {"gpio_i", "bus_rsp_o.data", "port_in"} | extra100, (got, extra100)
    fake = [{"Concept ID": "X", "Enters Through": ["not_a_name"], "Leaves Through": "also_not", "Held Lines": ["7", True]}]
    assert located_sets(m, fake, names, assign)["X"] == set()
    return {"C1 located": sorted(got), "names assigned at line 100": sorted(extra100)}


# ------------------------------------------------------------------------------------------------ main ---
def main():
    st = selftest()
    mods = modules()
    ref = reference(mods)
    names_by_m = {m: {x for (_, x) in chain.closed_names(m)} for m in mods}
    assign_by_m = {m: assign_lines(m) for m in mods}

    # union of located names per (arm, rep, module)
    union: dict[tuple[str, int, str], set[str] | None] = {}
    runs_present: dict[str, list[int]] = {}
    for arm in ARMS:
        for rep in RUNS:
            n_ok = 0
            for m in mods:
                ca = phase1_concepts(arm, rep, m)
                if ca is None:
                    union[(arm, rep, m)] = None
                    continue
                n_ok += 1
                u = set()
                for s in located_sets(m, ca, names_by_m[m], assign_by_m[m]).values():
                    u |= s
                union[(arm, rep, m)] = u
            if n_ok:
                runs_present.setdefault(arm, []).append(rep)

    def is_loc(arm, rep, m, el):
        u = union.get((arm, rep, m))
        return bool(u) and el in u

    out = {"self_test": st, "modules": len(mods), "reference_entries": len(ref),
           "reference_distinct_module_element": len({(m, e) for m, e, _ in ref}),
           "runs_present": runs_present, "per_arm": {}, "paired_vs_A": {}, "debug_dm": {}, "nine": {}}

    # per arm and run
    for arm in ARMS:
        rows = {}
        for rep in runs_present.get(arm, []):
            n_loc = sum(is_loc(arm, rep, m, e) for m, e, _ in ref)
            pairs = {(m, x) for m in mods for x in (union[(arm, rep, m)] or set())}
            missing = [m for m in mods if union[(arm, rep, m)] is None]
            rows[f"r{rep}"] = {"located_of_reference": n_loc, "distinct_located_module_name_pairs": len(pairs),
                               "distinct_located_name_strings": len({x for _, x in pairs}),
                               "modules_without_record": missing}
        tot = sum(r["located_of_reference"] for r in rows.values())
        den = len(ref) * len(rows)
        out["per_arm"][arm] = {"runs": rows, "pooled_located": tot, "pooled_denominator": den,
                               "pooled_share": round(tot / den, 4) if den else None}

    # paired per entry vs A
    a_counts = {(m, e, i): sum(is_loc(A, rep, m, e) for rep in runs_present.get(A, [])) for m, e, i in ref}
    for arm in ARMS:
        if arm == A:
            continue
        more = fewer = same = 0
        for m, e, i in ref:
            c = sum(is_loc(arm, rep, m, e) for rep in runs_present.get(arm, []))
            a = a_counts[(m, e, i)]
            if c > a:
                more += 1
            elif c < a:
                fewer += 1
            else:
                same += 1
        n = more + fewer
        out["paired_vs_A"][arm] = {"arm_more_runs": more, "arm_fewer_runs": fewer, "tied": same, "discordant": n,
                                   "binomial_two_sided_p": None if n == 0 else round(binom_two_sided(more, n), 4),
                                   "arm_runs": len(runs_present.get(arm, [])), "A_runs": len(runs_present.get(A, []))}
    out["A_runs_per_entry_histogram"] = dict(sorted(Counter(a_counts.values()).items()))

    # debug module
    dref = [(m, e, i) for m, e, i in ref if m == DEBUG]
    out["debug_dm"]["reference_entries"] = [(e, i) for _, e, i in dref]
    for arm in ARMS:
        out["debug_dm"][arm] = {}
        for rep in runs_present.get(arm, []):
            u = union[(arm, rep, DEBUG)]
            out["debug_dm"][arm][f"r{rep}"] = {
                "located_of_reference": sum(is_loc(arm, rep, m, e) for m, e, _ in dref),
                "distinct_located_names": None if u is None else len(u),
                "reference_located": sorted({e for m, e, _ in dref if is_loc(arm, rep, m, e)})}

    # the nine
    for m, e in NINE:
        key = f"{m} {e}"
        in_ref = sum(1 for mm, ee, _ in ref if (mm, ee) == (m, e))
        out["nine"][key] = {"reference_rows": in_ref}
        for arm in ARMS:
            out["nine"][key][arm] = "".join("1" if is_loc(arm, rep, m, e) else "0" for rep in runs_present.get(arm, []))

    (HERE / "verify_tier1.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
