"""Independent re-derivation of the "walk-found internal primaries" reading for two_phase_v9l and two_phase_v9j, per run.

Own code only: reads chain.closed_names (lab/chain.py) and the stored run files; imports none of the lab's run or
analysis scripts; sends no API call.

Definitions (as given for this check):
  reference rows  data/ground_truth/manual_gt_neorv32.json -> "modules" -> module -> "assets" rows with "element",
                  kept when the element is the name part of a key (entity, name) of chain.closed_names(module).
  listed rows     runs/<version>__v1/gpt-5.6-luna__high/r<k>/assets/<module>.json ["Assets"], field "Asset RTL".
  exact scorer    per module and run: Counter of listed names; reference rows walked in order; a row whose element still
                  has a copy consumes one and counts correct. listed = asset rows, findable = reference rows.
                  Row correctness: the first copies of a name in list order (as many as the reference consumed).
  anchored        for at least one concept id of the row ("Concepts"): the name is in that concept's "enters through"
                  or "leaves through", or the name's assignment lines intersect its "held lines".
                  assignment lines = union of "lines" of the counterpart entries under "gets value from", "decided by",
                  "reset by", "clocked by" of the closed-set record (lookup (row Entity, name) first, then any entity).
  internal        the part of the name before the first "." is not a port: its closed-set record has no "direction".
Reported: per version and run, the internal and not anchored rows split into correct / false; pooled totals; the same
by module group; the plain scorer totals as a cross-check.

  python -B walk_found.py            (writes walk_found.json next to it; prints the figures)
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
import chain  # noqa: E402  (closed_names only)

GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
SPLITS = LAB / "splits" / "tuning_v2.json"
VERSIONS = ("two_phase_v9l", "two_phase_v9j")
RUNS = (0, 1, 2)
MODEL = "gpt-5.6-luna__high"
ASSIGN_KEYS = ("gets value from", "decided by", "reset by", "clocked by")
_GT = None


def gt_modules() -> dict:
    global _GT
    if _GT is None:
        _GT = json.loads(GT.read_text(encoding="utf-8"))["modules"]
    return _GT


# ------------------------------------------------------------------------------------------------ inputs ---
def run_dir(version: str, k: int) -> Path:
    return LAB / "runs" / f"{version}__v1" / MODEL / f"r{k}"


def reference_rows(m: str) -> list[str]:
    """The reference elements of a module, in order, kept when the element is a closed-set name."""
    gt = gt_modules()
    if m not in gt:
        return []
    names = {n for (_e, n) in chain.closed_names(m)}
    return [r["element"] for r in gt[m]["assets"] if r["element"] in names]


def groups() -> dict[str, list[str]]:
    tuning_dirs = sorted(p.name for p in (LAB / "inputs" / "v1" / "tuning").iterdir() if p.is_dir())
    heldout_dirs = sorted(p.name for p in (LAB / "inputs" / "v1" / "heldout").iterdir() if p.is_dir())
    tuning15 = [m for m in tuning_dirs if reference_rows(m)]
    sp = json.loads(SPLITS.read_text(encoding="utf-8"))
    return {"tuning 15": tuning15, "held-out 26": heldout_dirs, "tuning_v2": list(sp["tuning"]),
            "heldout_v2": list(sp["heldout"]), "all 41": sorted(set(tuning15) | set(heldout_dirs))}


# ------------------------------------------------------------------------------------------------ scorer ---
def score(listed: list[str], reference: list[str]) -> tuple[int, list[bool]]:
    """Exact scorer: returns (correct, per-listed-row correctness flags)."""
    left = Counter(listed)
    consumed: Counter = Counter()
    correct = 0
    for el in reference:
        if left[el] > 0:
            left[el] -= 1
            consumed[el] += 1
            correct += 1
    flags, seen = [], Counter()
    for n in listed:
        seen[n] += 1
        flags.append(seen[n] <= consumed[n])
    return correct, flags


# ------------------------------------------------------------------------------------------------ classes ---
def lookup(names: dict, entity: str, name: str) -> tuple[dict | None, str]:
    """(record, how): the closed-set record of (entity, name), else of any entity with that name (first in key order)."""
    if (entity, name) in names:
        return names[(entity, name)], "entity"
    for (_e, n), rec in names.items():
        if n == name:
            return rec, "name-only"
    return None, "missing"


def assignment_lines(rec: dict | None) -> set[int]:
    if rec is None:
        return set()
    out: set[int] = set()
    for key in ASSIGN_KEYS:
        for x in rec.get("counterparts", {}).get(key, []):
            out |= {int(line) for line in x.get("lines", [])}
    return out


def anchored(row: dict, concepts: dict[str, dict], names: dict) -> tuple[bool, str]:
    name, ent = row["Asset RTL"], row["Entity"]
    rec, how = lookup(names, ent, name)
    lines = assignment_lines(rec)
    for cid in row.get("Concepts", []):
        c = concepts.get(cid)
        if c is None:
            continue
        if name in c.get("enters through", []) or name in c.get("leaves through", []):
            return True, how
        if lines & {int(line) for line in c.get("held lines", []) if isinstance(line, int)}:
            return True, how
    return False, how


def internal(row: dict, names: dict) -> tuple[bool, str]:
    top = row["Asset RTL"].split(".")[0]
    rec, how = lookup(names, row["Entity"], top)
    return (rec is not None and "direction" not in rec), how


def phase1_concepts(version: str, k: int, m: str) -> dict[str, dict]:
    p1 = json.loads((run_dir(version, k) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
    ca = p1.get("reply", {}).get("conceptual assets") if isinstance(p1.get("reply"), dict) else None
    if not isinstance(ca, list):
        return {}
    return {c["id"]: c for c in ca if isinstance(c, dict) and "id" in c}


def listed_rows(version: str, k: int, m: str) -> list[dict]:
    return json.loads((run_dir(version, k) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]


def classify_module(version: str, k: int, m: str) -> list[dict]:
    names = chain.closed_names(m)
    rows = listed_rows(version, k, m)
    concepts = phase1_concepts(version, k, m)
    _correct, flags = score([r["Asset RTL"] for r in rows], reference_rows(m))
    out = []
    for r, ok in zip(rows, flags):
        anc, how_a = anchored(r, concepts, names)
        internal_, how_i = internal(r, names)
        out.append({"module": m, "entity": r["Entity"], "name": r["Asset RTL"], "concepts": list(r.get("Concepts", [])),
                    "correct": ok, "anchored": anc, "internal": internal_, "lookup": how_a, "top lookup": how_i,
                    "no concept record": [c for c in r.get("Concepts", []) if c not in concepts],
                    "occurrence hit": occurrence_hit(r, concepts, names)})
    return out


def occurrence_hit(row: dict, concepts: dict[str, dict], names: dict) -> bool:
    """Side figure, not part of the given definition: the name's closed-set "occurrence lines" meet a held line of one
    of its concepts (catches constant assignments such as `x <= '0'`, which have no counterpart entry)."""
    rec, _ = lookup(names, row["Entity"], row["Asset RTL"])
    occ = {int(line) for line in (rec or {}).get("occurrence lines", [])}
    for cid in row.get("Concepts", []):
        c = concepts.get(cid)
        if c and occ & {int(line) for line in c.get("held lines", []) if isinstance(line, int)}:
            return True
    return False


# ------------------------------------------------------------------------------------------------ self-test ---
def selftest() -> list[str]:
    """Hand-read expectations; any failure stops the report."""
    fails = []

    def check(label, cond):
        if not cond:
            fails.append(label)

    # 1. the exact scorer on hand-made cases
    c, f = score(["a", "a", "b", "c"], ["a", "a", "a", "d"])
    check("scorer synthetic correct=2", c == 2)
    check("scorer synthetic flags [T,T,F,F]", f == [True, True, False, False])
    c, f = score(["x", "y", "x"], ["x"])
    check("scorer first copy only", c == 1 and f == [True, False, False])
    # 2. closed-set assignment lines against hand-read RTL (inputs/v1/tuning/neorv32_bus/rtl.txt):
    #    48 "if (rstn_i = '0') then", 54 "elsif rising_edge(clk_i) then", 55 "state  <= state_nxt;"
    names = chain.closed_names("neorv32_bus")
    rec, how = lookup(names, "neorv32_bus_switch", "state")
    check("bus_switch.state lookup by entity", how == "entity")
    check("bus_switch.state assignment lines {48,54,55}", assignment_lines(rec) == {48, 54, 55})
    rtl = {}
    for line in (LAB / "inputs" / "v1" / "tuning" / "neorv32_bus" / "rtl.txt").read_text(encoding="utf-8").splitlines():
        num, _, rest = line.partition("|")
        if num.strip().isdigit():
            rtl[int(num)] = rest.strip()
    check("RTL 48 is the reset condition", rtl.get(48, "").startswith("if (rstn_i = '0')"))
    check("RTL 54 is the clock edge", rtl.get(54, "").startswith("elsif rising_edge(clk_i)"))
    check("RTL 55 assigns state", rtl.get(55, "").startswith("state  <= state_nxt"))
    # sel: only "decided by" counterparts (83, 112, 113, 117, 123, 127); its constant assignments (79, 87) have none
    rec, _ = lookup(names, "neorv32_bus_switch", "sel")
    check("bus_switch.sel assignment lines", assignment_lines(rec) == {83, 112, 113, 117, 123, 127})
    check("RTL 79 assigns sel a constant", rtl.get(79, "").startswith("sel        <= '0'"))
    # 3. internal: signals and record-signal fields yes; ports and port fields no
    check("state internal", internal({"Entity": "neorv32_bus_switch", "Asset RTL": "state"}, names)[0])
    check("keeper.busy internal", internal({"Entity": "neorv32_bus_gateway", "Asset RTL": "keeper.busy"}, names)[0])
    check("clk_i not internal", not internal({"Entity": "neorv32_bus_switch", "Asset RTL": "clk_i"}, names)[0])
    check("a_req_i.addr not internal", not internal({"Entity": "neorv32_bus_switch", "Asset RTL": "a_req_i.addr"}, names)[0])
    # 4. v9j r0 neorv32_bus, hand-read from phase1/neorv32_bus.json and assets/neorv32_bus.json:
    #    C1 (bus_switch) enters [] leaves [] held [55,79,87,99,114,118,124,128]; C3 held has 419; C6 held has 839;
    #    C8 (amo_rvs) held [955,957]. Reference: a_req b_req sel port_sel stb keeper.err keeper.halt keeper.cnt state state alu_res
    rows = classify_module("two_phase_v9j", 0, "neorv32_bus")
    byname = {(r["entity"], r["name"]): r for r in rows}
    check("v9j r0 bus 14 listed", len(rows) == 14)
    check("v9j r0 bus 11 findable", len(reference_rows("neorv32_bus")) == 11)
    check("v9j r0 bus 8 correct", sum(r["correct"] for r in rows) == 8)
    s = byname[("neorv32_bus_switch", "state")]
    check("state anchored via line 55 in C1 held; internal; correct", s["anchored"] and s["internal"] and s["correct"])
    s = byname[("neorv32_bus_switch", "sel")]
    check("sel not anchored (C1 held has none of 83,112,113,117,123,127; enters/leaves empty); internal; correct",
          not s["anchored"] and s["internal"] and s["correct"])
    s = byname[("neorv32_bus_amo_rvs", "sc_fail")]
    check("sc_fail anchored via 957 in C8 held; internal; false", s["anchored"] and s["internal"] and not s["correct"])
    s = byname[("neorv32_bus_gateway", "keeper.busy")]
    check("keeper.busy anchored via 419 in C3 held; internal; false", s["anchored"] and s["internal"] and not s["correct"])
    s = byname[("neorv32_bus_amo_rmw", "alu_res")]
    check("alu_res anchored via 839 in C6 held; internal; correct", s["anchored"] and s["internal"] and s["correct"])
    check("amo_rvs.state correct (second reference copy of state)", byname[("neorv32_bus_amo_rvs", "state")]["correct"])
    # hand-derived from the closed set and the phase-1 held lines, all 14 rows:
    #   keeper.err  lines {408,414,417,423} vs C3 held {409,411,412,413,415,416,418,419,422,424,425}: none  -> walk-found, correct
    #   keeper.lock lines {408,414,417,420} vs C3 held: none                                              -> walk-found, false
    #   amo_rvs state lines {903,905,906,910,911,920,926} vs C7 held {904,912,914,921,927}: none          -> walk-found, correct
    #   port_sel 356/357/358/361 in C2 held; keeper.cnt 422, keeper.halt 416 in C3 held; arbiter.* 763 in C5/C6 held -> anchored
    check("v9j r0 bus walk-found internal = sel, keeper.err, keeper.lock, state (3 correct / 1 false)",
          [(r["name"], r["correct"]) for r in rows if r["internal"] and not r["anchored"]]
          == [("sel", True), ("keeper.err", True), ("keeper.lock", False), ("state", True)])
    # side figure: keeper.err occurs on held lines 412, 415, 424 (constant assignments) -> occurrence-hit
    check("keeper.err occurrence lines hit a held line", byname[("neorv32_bus_gateway", "keeper.err")]["occurrence hit"])
    check("keeper.lock occurrence lines (420, 426) miss the held lines", not byname[("neorv32_bus_gateway", "keeper.lock")]["occurrence hit"])
    return fails


# ------------------------------------------------------------------------------------------------ report ---
def summarize(rows: list[dict], G: dict, runs: int) -> dict:
    s: dict = {}
    for g, ms in G.items():
        ms = set(ms)
        rr = [r for r in rows if r["module"] in ms]
        wf = [r for r in rr if r["internal"] and not r["anchored"]]
        ai = [r for r in rr if r["internal"] and r["anchored"]]
        po = [r for r in rr if not r["internal"]]
        s[g] = {"listed": len(rr), "correct": sum(r["correct"] for r in rr),
                "findable": runs * sum(len(reference_rows(m)) for m in ms),
                "walk-found internal correct": sum(r["correct"] for r in wf),
                "walk-found internal false": sum(not r["correct"] for r in wf),
                "anchored internal correct": sum(r["correct"] for r in ai),
                "anchored internal false": sum(not r["correct"] for r in ai),
                "port correct": sum(r["correct"] for r in po), "port false": sum(not r["correct"] for r in po),
                "side: walk-found internal with an occurrence line on a held line, correct": sum(r["correct"] for r in wf if r["occurrence hit"]),
                "side: walk-found internal with an occurrence line on a held line, false": sum(not r["correct"] for r in wf if r["occurrence hit"])}
    s["name-only lookups"] = sum(r["lookup"] == "name-only" or r["top lookup"] == "name-only" for r in rows)
    s["missing lookups"] = sum(r["lookup"] == "missing" or r["top lookup"] == "missing" for r in rows)
    s["rows with a concept id absent from phase 1"] = sum(bool(r["no concept record"]) for r in rows)
    return s


def main() -> None:
    fails = selftest()
    if fails:
        print("SELF-TEST FAILED:", *fails, sep="\n  ")
        sys.exit(1)
    print("self-test PASS")
    G = groups()
    modules = G["all 41"]
    out = {"definitions": "see the module docstring", "groups": {g: len(ms) for g, ms in G.items()},
           "findable per run": {g: sum(len(reference_rows(m)) for m in ms) for g, ms in G.items()},
           "modules": {g: ms for g, ms in G.items()}, "per version": {}}
    print("groups (modules):", out["groups"])
    print("findable per run (reference rows kept):", out["findable per run"])
    for v in VERSIONS:
        V: dict = {"per run": {}, "pooled": {}, "walk-found internal rows": []}
        pooled_rows = []
        for k in RUNS:
            rows = []
            for m in modules:
                rows += classify_module(v, k, m)
            pooled_rows += rows
            V["per run"][f"r{k}"] = summarize(rows, G, 1)
            V["walk-found internal rows"] += [{"run": f"r{k}", **{kk: r[kk] for kk in ("module", "entity", "name", "concepts", "correct")}}
                                              for r in rows if r["internal"] and not r["anchored"]]
        V["pooled"] = summarize(pooled_rows, G, len(RUNS))
        out["per version"][v] = V
    (HERE / "walk_found.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for v in VERSIONS:
        print(f"\n== {v} ==")
        for k in RUNS:
            s = out["per version"][v]["per run"][f"r{k}"]
            a = s["all 41"]
            print(f" r{k} all 41: listed {a['listed']} correct {a['correct']} findable {a['findable']} | internal & not anchored: "
                  f"correct {a['walk-found internal correct']} false {a['walk-found internal false']} | "
                  f"name-only lookups {s['name-only lookups']}, missing lookups {s['missing lookups']}, "
                  f"concept ids absent {s['rows with a concept id absent from phase 1']}")
        a = out["per version"][v]["pooled"]["all 41"]
        print(f" pooled all 41: listed {a['listed']} correct {a['correct']} findable {a['findable']} | internal & not anchored: "
              f"correct {a['walk-found internal correct']} false {a['walk-found internal false']}")
        print(f"   side figure (not the given definition): of those, name occurs on a held line: "
              f"correct {a['side: walk-found internal with an occurrence line on a held line, correct']} "
              f"false {a['side: walk-found internal with an occurrence line on a held line, false']}")
        for g in ("tuning 15", "held-out 26", "tuning_v2", "heldout_v2"):
            for k in RUNS:
                a = out["per version"][v]["per run"][f"r{k}"][g]
                print(f"   {g:11s} r{k}: listed {a['listed']} correct {a['correct']} findable {a['findable']} | walk-found internal "
                      f"correct {a['walk-found internal correct']} false {a['walk-found internal false']}")
            a = out["per version"][v]["pooled"][g]
            print(f"   {g:11s} pooled: listed {a['listed']} correct {a['correct']} findable {a['findable']} | walk-found internal "
                  f"correct {a['walk-found internal correct']} false {a['walk-found internal false']} | anchored internal "
                  f"correct {a['anchored internal correct']} false {a['anchored internal false']} | ports correct {a['port correct']} false {a['port false']}")


if __name__ == "__main__":
    main()
