"""Independent re-count of the LOCATED coverage of the reference (Tier 2c check).

Re-implements the LOCATED rule from the raw Phase 1 replies (not chain.located), scores it against the manual ground
truth restricted to closed-set names, and compares each of the two orders (O4, O5) against the working version W.
No API calls. Reads only JSON files on disk plus chain.closed_names / chain.run_dir.

  python -B verify_tier2c.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
ROOT = Path(r"E:\jobs\ff\test\Prepoison_subset")
LAB = ROOT / "experiments" / "03_two_phase_csa_pio" / "lab"
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (closed_names and run_dir only)

GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
HELDOUT = LAB / "inputs" / "v1" / "heldout"
MODEL, EFFORT = "gpt-5.6-luna", "high"
W = "two_phase_p1o_first"
ORDERS = ["two_phase_p1t2_O4", "two_phase_p1t2_O5"]
VERSIONS = [W] + ORDERS
RUNS = [0, 1, 2]
ASSIGN_KEYS = ("gets value from", "decided by", "reset by", "clocked by")

SPOT = [  # (module, name) pairs to report per version and run
    ("neorv32_debug_dm", "ndmrstn_o"),
    ("neorv32_xbus", "xbus_dat_i"), ("neorv32_xbus", "xbus_stb_o"),
    ("neorv32_cpu_lsu", "err_o"),
    ("neorv32_gpio", "port_in"),
    ("neorv32_cpu_cp_cond", "ctrl_i"),
    ("neorv32_cpu_counters", "sel"), ("neorv32_cpu_counters", "cnt_en"), ("neorv32_cpu_counters", "rdata_o"),
]


# ------------------------------------------------------------------------------------------------ inputs ---
def modules() -> list[str]:
    return sorted(p.name for p in HELDOUT.iterdir() if p.is_dir())


def names_and_assign(m: str) -> tuple[set[str], dict[str, set[int]]]:
    """Closed-set names of the module (any entity) and, per name, the union of its assignment lines over every entity
    carrying the name: the integer "lines" of its counterparts under the four assignment keys."""
    cn = chain.closed_names(m)
    names = {x for (_, x) in cn}
    assign: dict[str, set[int]] = defaultdict(set)
    for (_, x), entry in cn.items():
        cps = entry.get("counterparts") or {}
        for key in ASSIGN_KEYS:
            for c in cps.get(key, []) or []:
                if isinstance(c, dict):
                    assign[x].update(l for l in (c.get("lines") or []) if isinstance(l, int) and not isinstance(l, bool))
    return names, dict(assign)


def reference(m: str, names: set[str]) -> list[str]:
    """The module's reference elements that are closed-set names (duplicates kept as separate entries if present)."""
    gt = json.load(open(GT, encoding="utf-8"))["modules"][m]
    return [row["element"] for row in gt["assets"] if row["element"] in names]


def phase1_concepts(version: str, rep: int, m: str) -> list[dict]:
    p = chain.run_dir(version, MODEL, rep, EFFORT) / "phase1" / f"{m}.json"
    raw = json.load(open(p, encoding="utf-8"))["raw"]
    j = json.loads(raw)
    cas = j.get("Conceptual Assets")
    return [c for c in cas if isinstance(c, dict)] if isinstance(cas, list) else []


def _lst(v):
    return v if isinstance(v, list) else ([v] if isinstance(v, (str, int)) else [])


def located_names(concepts: list[dict], names: set[str], assign: dict[str, set[int]]) -> tuple[set[str], int]:
    """Union over entries of the LOCATED rule; also the number of non-integer Held Lines values ignored."""
    out: set[str] = set()
    non_int = 0
    for c in concepts:
        ports = [p for p in _lst(c.get("Enters Through")) + _lst(c.get("Leaves Through")) if isinstance(p, str)]
        held = set()
        for l in _lst(c.get("Held Lines")):
            if isinstance(l, int) and not isinstance(l, bool):
                held.add(l)
            else:
                non_int += 1
        out |= {p for p in ports if p in names}
        out |= {x for x, ls in assign.items() if ls & held}
    return out, non_int


# ------------------------------------------------------------------------------------------------ stats ---
def binom_two_sided(k: int, n: int) -> float:
    """Exact two-sided binomial test, p = 1/2: sum of P(X = i) over every i whose probability is <= P(X = k)."""
    if n == 0:
        return 1.0
    pk = math.comb(n, k)
    total = sum(math.comb(n, i) for i in range(n + 1) if math.comb(n, i) <= pk)
    return min(1.0, total / 2 ** n)


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest() -> None:
    # LOCATED rule on a hand-built case.
    names = {"a", "b", "c", "d"}
    assign = {"a": {10, 11}, "b": {20}, "c": set()}
    concepts = [{"Enters Through": ["d", "zz"], "Leaves Through": "c", "Held Lines": [11, "20"]},
                {"Held Lines": [99]}, "junk"]
    got, non_int = located_names([c for c in concepts if isinstance(c, dict)], names, assign)
    assert got == {"d", "c", "a"}, got            # "20" is a string -> ignored, so b is not located
    assert non_int == 1, non_int
    # Binomial: k=0 of n=3 -> 2/8; k=1 of n=1 -> 1; k=2 of n=4 -> 1; k=5 of n=6 -> 14/64.
    assert abs(binom_two_sided(0, 3) - 0.25) < 1e-12
    assert abs(binom_two_sided(1, 1) - 1.0) < 1e-12
    assert abs(binom_two_sided(2, 4) - 1.0) < 1e-12
    assert abs(binom_two_sided(5, 6) - 14 / 64) < 1e-12
    # Hand-read anchor: W r0 neorv32_debug_dm, concept C1 has Leaves Through ["dmi_rsp_o.data"] and Held Lines
    # [745, 754]; the reply text says auth.valid is produced at line 745. The closed set must give auth.valid an
    # assignment line 745, and dmi_rsp_o.data must be a closed-set name.
    names_dm, assign_dm = names_and_assign("neorv32_debug_dm")
    assert "dmi_rsp_o.data" in names_dm
    assert 745 in assign_dm.get("auth.valid", set()), sorted(assign_dm.get("auth.valid", set()))
    c1 = [c for c in phase1_concepts(W, 0, "neorv32_debug_dm") if c.get("Concept ID") == "C1"][0]
    assert c1["Leaves Through"] == ["dmi_rsp_o.data"] and c1["Held Lines"] == [745, 754], c1
    loc1, _ = located_names([c1], names_dm, assign_dm)
    assert {"dmi_rsp_o.data", "auth.valid"} <= loc1, loc1
    print("selftest PASS")


# ------------------------------------------------------------------------------------------------ main ---
def main() -> None:
    selftest()
    mods = modules()
    print(f"\nheld-out modules: {len(mods)}")
    per_mod = {m: names_and_assign(m) for m in mods}
    ref = {m: reference(m, per_mod[m][0]) for m in mods}
    n_ref = sum(len(v) for v in ref.values())
    n_ref_pairs = len({(m, x) for m, v in ref.items() for x in v})
    print(f"reference entries (element in closed set): {n_ref}  distinct (module, name): {n_ref_pairs}")
    dup = [(m, x) for m, v in ref.items() for x in set(v) if v.count(x) > 1]
    if dup:
        print(f"  duplicate reference pairs: {dup}")
    print(f"  per module: " + ", ".join(f"{m.replace('neorv32_', '')}={len(ref[m])}" for m in mods))

    # located sets: loc[version][rep][module] -> set of names
    loc: dict[str, dict[int, dict[str, set[str]]]] = {}
    non_int_total = 0
    for v in VERSIONS:
        loc[v] = {}
        for k in RUNS:
            d = chain.run_dir(v, MODEL, k, EFFORT) / "phase1"
            if not d.exists():
                continue
            loc[v][k] = {}
            for m in mods:
                if not (d / f"{m}.json").exists():
                    print(f"  MISSING {v} r{k} {m}")
                    continue
                s, ni = located_names(phase1_concepts(v, k, m), *per_mod[m])
                non_int_total += ni
                loc[v][k][m] = s
    print(f"non-integer Held Lines values ignored: {non_int_total}")

    # ---- per version and run
    print("\n== per version and run: reference located / distinct located pairs")
    hits: dict[str, dict[int, dict[tuple[str, int, str], bool]]] = {}   # version -> rep -> (m, idx, name) -> located
    for v in VERSIONS:
        hits[v] = {}
        pooled_hit = pooled_n = 0
        for k, runs in sorted(loc[v].items()):
            h = {}
            for m in mods:
                if m not in runs:
                    continue
                for i, x in enumerate(ref[m]):
                    h[(m, i, x)] = x in runs[m]
            hits[v][k] = h
            n_loc = sum(h.values())
            n_pairs = sum(len(s) for s in runs.values())
            pooled_hit += n_loc
            pooled_n += len(h)
            print(f"  {v:24s} r{k}: located {n_loc}/{len(h)}  ({n_loc / len(h):.3f})   distinct located pairs {n_pairs}")
        print(f"  {v:24s} pooled over {len(loc[v])} runs: {pooled_hit}/{pooled_n} = {pooled_hit / pooled_n:.3f}")

    # ---- per order vs W, per reference entry: runs located (0-3)
    print("\n== per order against W (runs located per reference entry, 0-3)")
    keys = [(m, i, x) for m in mods for i, x in enumerate(ref[m])]

    def runs_located(v, key):
        return sum(1 for k in hits[v] if hits[v][k].get(key, False))

    cw = {key: runs_located(W, key) for key in keys}
    print(f"  W ({W}) runs present: {sorted(hits[W])}; entries by runs located: "
          + ", ".join(f"{r}: {sum(1 for key in keys if cw[key] == r)}" for r in range(4)))
    for v in ORDERS:
        cv = {key: runs_located(v, key) for key in keys}
        more = [key for key in keys if cv[key] > cw[key]]
        fewer = [key for key in keys if cv[key] < cw[key]]
        same = len(keys) - len(more) - len(fewer)
        n_disc = len(more) + len(fewer)
        p = binom_two_sided(len(more), n_disc)
        print(f"  {v}: runs present {sorted(hits[v])}; entries by runs located: "
              + ", ".join(f"{r}: {sum(1 for key in keys if cv[key] == r)}" for r in range(4)))
        print(f"    more than W: {len(more)}  fewer than W: {len(fewer)}  same: {same}  "
              f"discordant {n_disc}  two-sided exact binomial p = {p:.4f}")
        print(f"    total runs-located sum: {v} {sum(cv.values())} vs W {sum(cw.values())} (of {len(keys)}x3 = {3 * len(keys)})")
        if more:
            print("    gained (name: order runs vs W runs): " + "; ".join(f"{m.replace('neorv32_', '')}.{x} {cv[key]}v{cw[key]}" for key in more for (m, i, x) in [key]))
        if fewer:
            print("    lost   (name: order runs vs W runs): " + "; ".join(f"{m.replace('neorv32_', '')}.{x} {cv[key]}v{cw[key]}" for key in fewer for (m, i, x) in [key]))

    # ---- debug module per version and run
    dm = "neorv32_debug_dm"
    print(f"\n== {dm}: reference entries {len(ref[dm])}: {ref[dm]}")
    for v in VERSIONS:
        for k in sorted(loc[v]):
            s = loc[v][k].get(dm, set())
            got = [x for x in ref[dm] if x in s]
            print(f"  {v:24s} r{k}: located ref {len(got)}/{len(ref[dm])} {got}; distinct located names {len(s)}; "
                  f"ndmrstn_o {'LOCATED' if 'ndmrstn_o' in s else 'not located'}")

    # ---- spot checks
    print("\n== spot checks (Y = located, n = not located; order r0 r1 r2)")
    for v in VERSIONS:
        print(f"  {v}:")
        for m, x in SPOT:
            in_ref = x in ref.get(m, [])
            in_cs = x in per_mod[m][0]
            marks = " ".join(("Y" if x in loc[v][k].get(m, set()) else "n") for k in sorted(loc[v]))
            print(f"    {m}.{x:12s} {marks}   (closed set: {'yes' if in_cs else 'NO'}; in reference: {'yes' if in_ref else 'no'})")


if __name__ == "__main__":
    main()
