"""Independent re-count of the Phase 1 LOCATED readings for the tier-2 arms (r0 only, held-out 26).

Reads only: the closed sets (through chain.closed_names), the Phase 1 records on disk (their "raw" reply),
and the manual reference. Re-implements the LOCATED rule; never calls chain.located and never sends a call.
Base arm for the paired counts: two_phase_p1o_first.

Run:  python -B verify_located.py        (prints a JSON block; also saves verify_located.json next to this file)
"""
from __future__ import annotations

import json
import os
import sys
from fractions import Fraction
from math import comb
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]                       # .../experiments/03_two_phase_csa_pio/lab
ROOT = LAB.parents[2]                       # .../Prepoison_subset
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (only chain.closed_names and chain.run_dir are used)

MODEL, EFFORT, REP = "gpt-5.6-luna", "high", 0
BASE = "two_phase_p1o_first"
ARMS = ["two_phase_p1o_first", "two_phase_p1o_first2", "two_phase_p1t2_O1", "two_phase_p1t2_O2",
        "two_phase_p1t2_O3", "two_phase_p1t2_O4", "two_phase_p1t2_O5"]
GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
HELDOUT = LAB / "inputs" / "v1" / "heldout"
DEBUG = "neorv32_debug_dm"
ASSIGN_KEYS = ("gets value from", "decided by", "reset by", "clocked by")
USED_KEYS = ("Concept ID", "Enters Through", "Leaves Through", "Held Lines")

PROBLEMS: list[str] = []
NON_INT = {"counterpart lines": 0, "held lines": 0}


def is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


# ------------------------------------------------------------------------------------------ closed set ---
def closed_info(m: str) -> tuple[set[str], dict[str, set[int]]]:
    """names: every closed-set name of the module (any entity). assign: name -> its assignment lines."""
    cn = chain.closed_names(m)
    names = {x for (_, x) in cn}
    assign: dict[str, set[int]] = {x: set() for x in names}
    for (_, x), entry in cn.items():
        cps = entry.get("counterparts") or {}
        for key in ASSIGN_KEYS:
            for c in cps.get(key, []) or []:
                if not isinstance(c, dict):
                    continue
                for l in c.get("lines") or []:
                    if is_int(l):
                        assign[x].add(l)
                    else:
                        NON_INT["counterpart lines"] += 1
    return names, assign


# ------------------------------------------------------------------------------------------ records ---
def dup_hook(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen and k in USED_KEYS:
            dup_hook.dups.append((k, seen[k] == v))
        seen[k] = v                        # last value wins, as json.loads does
    return seen


dup_hook.dups = []


def load_concepts(path: Path) -> list[dict] | None:
    """The 'Conceptual Assets' list of a record's raw reply, or None when it cannot be read."""
    rec = json.loads(path.read_text(encoding="utf-8"))
    raw = rec.get("raw")
    if not isinstance(raw, str):
        PROBLEMS.append(f"{path}: 'raw' is not a string")
        return None
    text = raw.strip()
    try:
        obj = json.loads(text, object_pairs_hook=dup_hook)
    except json.JSONDecodeError:
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
            text = text.rsplit("```", 1)[0]
        try:
            obj = json.loads(text, object_pairs_hook=dup_hook)
        except json.JSONDecodeError as e:
            PROBLEMS.append(f"{path}: raw reply is not JSON ({e})")
            return None
    ca = obj.get("Conceptual Assets") if isinstance(obj, dict) else None
    if not isinstance(ca, list):
        PROBLEMS.append(f"{path}: no 'Conceptual Assets' list in raw")
        return None
    return [c for c in ca if isinstance(c, dict)]


def lst(v) -> list:
    return v if isinstance(v, list) else ([v] if isinstance(v, str) else [])


def entry_located(c: dict, names: set[str], assign: dict[str, set[int]]) -> set[str]:
    """LOCATED set of one Phase 1 entry (the rule under test)."""
    ports = [p for p in lst(c.get("Enters Through")) + lst(c.get("Leaves Through")) if isinstance(p, str)]
    held = set()
    for l in lst(c.get("Held Lines")):
        if is_int(l):
            held.add(l)
        else:
            NON_INT["held lines"] += 1
    return {p for p in ports if p in names} | {x for x, ls in assign.items() if ls & held}


def module_located(version: str, m: str, names, assign) -> set[str] | None:
    """Union of the LOCATED sets of the module's reply; None when the module has no record."""
    path = chain.run_dir(version, MODEL, REP, EFFORT) / "phase1" / f"{m}.json"
    if not path.exists():
        return None
    concepts = load_concepts(path)
    if concepts is None:
        return set()
    out: set[str] = set()
    for c in concepts:
        out |= entry_located(c, names, assign)
    return out


# ------------------------------------------------------------------------------------------ stats ---
def binom_two_sided(b: int, c: int) -> float:
    """Exact two-sided binomial test of b vs c discordant pairs at p = 1/2."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = Fraction(sum(comb(n, i) for i in range(k + 1)), 2 ** n)
    return float(min(Fraction(1), 2 * tail))


# ------------------------------------------------------------------------------------------ self-test ---
def selftest(info: dict) -> None:
    """Hand-read lines (2026-10-19): two_phase_p1o_first r0 debug_dm C1 has Enters [], Leaves ['dmi_rsp_o.data'],
    Held [745, 754]; closed set: auth.valid gets its value at 745; ndmrstn_o is decided only at 505;
    dm_reg.hartsel is assigned at 429/424/425/397/414. Expected: C1 locates auth.valid and dmi_rsp_o.data,
    not ndmrstn_o, not dm_reg.hartsel."""
    names, assign = info[DEBUG]
    path = chain.run_dir(BASE, MODEL, REP, EFFORT) / "phase1" / f"{DEBUG}.json"
    concepts = load_concepts(path)
    c1 = next(c for c in concepts if c.get("Concept ID") == "C1")
    assert lst(c1.get("Enters Through")) == [] and lst(c1.get("Leaves Through")) == ["dmi_rsp_o.data"], c1
    assert lst(c1.get("Held Lines")) == [745, 754], c1.get("Held Lines")
    assert assign["auth.valid"] == {745}, assign["auth.valid"]
    assert assign["ndmrstn_o"] == {505}, assign["ndmrstn_o"]
    assert assign["dm_reg.hartsel"] == {429, 424, 425, 397, 414}, assign["dm_reg.hartsel"]
    loc = entry_located(c1, names, assign)
    assert {"auth.valid", "dmi_rsp_o.data"} <= loc, loc
    assert "ndmrstn_o" not in loc and "dm_reg.hartsel" not in loc, loc
    # binomial: 3 vs 0 -> 2 * (1/8) = 0.25 ; 0 vs 0 -> 1 ; 5 vs 5 -> 1 ; 8 vs 1 -> 2 * (1 + 9) / 512
    assert abs(binom_two_sided(3, 0) - 0.25) < 1e-12
    assert binom_two_sided(0, 0) == 1.0 and binom_two_sided(5, 5) == 1.0
    assert abs(binom_two_sided(8, 1) - 2 * (1 + 9) / 512) < 1e-12


# ------------------------------------------------------------------------------------------ main ---
def main() -> dict:
    modules = sorted(p.name for p in HELDOUT.iterdir() if p.is_dir())
    info = {m: closed_info(m) for m in modules}
    selftest(info)

    gt = json.loads(GT.read_text(encoding="utf-8"))["modules"]
    ref: list[tuple[str, str]] = []
    dropped = 0
    for m in modules:
        names, _ = info[m]
        for row in gt[m]["assets"]:
            el = row.get("element")
            if el in names:
                ref.append((m, el))
            else:
                dropped += 1
    n_ref = len(ref)
    debug_ref = [(m, e) for (m, e) in ref if m == DEBUG]

    located: dict[str, dict[str, set[str] | None]] = {}
    for arm in ARMS:
        located[arm] = {m: module_located(arm, m, *info[m]) for m in modules}

    def hit(arm: str, m: str, e: str) -> bool:
        s = located[arm][m]
        return s is not None and e in s

    base_hits = {(m, e): hit(BASE, m, e) for (m, e) in ref}
    figures: dict = {
        "self-test": "PASS",
        "modules": len(modules), "reference entries (closed-set rows)": n_ref,
        "reference rows dropped (element not a closed-set name)": dropped,
        "debug module reference entries": len(debug_ref),
        "base arm": BASE, "run": f"{MODEL}__{EFFORT}/r{REP}", "arms": {},
    }
    for arm in ARMS:
        with_rec = [m for m in modules if located[arm][m] is not None]
        missing = [m for m in modules if located[arm][m] is None]
        arm_hits = {(m, e): hit(arm, m, e) for (m, e) in ref}
        n_loc = sum(arm_hits.values())
        pairs = sum(len(s) for s in located[arm].values() if s is not None)
        b = sum(1 for k in ref if arm_hits[k] and not base_hits[k])
        c = sum(1 for k in ref if base_hits[k] and not arm_hits[k])
        common = [k for k in ref if located[arm][k[0]] is not None and located[BASE][k[0]] is not None]
        b2 = sum(1 for k in common if arm_hits[k] and not base_hits[k])
        c2 = sum(1 for k in common if base_hits[k] and not arm_hits[k])
        dbg = located[arm][DEBUG]
        figures["arms"][arm] = {
            "modules with a record": len(with_rec), "modules missing": missing,
            "reference entries located": n_loc, "of": n_ref,
            "distinct located (module, name) pairs": pairs,
            "vs base: arm yes base no": b, "vs base: base yes arm no": c,
            "vs base: two-sided exact binomial p": binom_two_sided(b, c),
            "vs base on modules with records in both: entries": len(common),
            "vs base on modules with records in both: arm yes base no": b2,
            "vs base on modules with records in both: base yes arm no": c2,
            "vs base on modules with records in both: p": binom_two_sided(b2, c2),
            "debug_dm: record": dbg is not None,
            "debug_dm: reference located": sum(1 for (m, e) in debug_ref if hit(arm, m, e)),
            "debug_dm: of": len(debug_ref),
            "debug_dm: reference located names": sorted(e for (m, e) in debug_ref if hit(arm, m, e)),
            "debug_dm: distinct located names": len(dbg) if dbg is not None else None,
            "debug_dm: distinct located name list": sorted(dbg) if dbg is not None else None,
            "debug_dm: ndmrstn_o located": (dbg is not None and "ndmrstn_o" in dbg),
        }
    figures["non-integer line values skipped"] = dict(NON_INT)
    figures["duplicate used keys inside one raw object (key, same value)"] = [list(x) for x in dup_hook.dups]
    figures["problems"] = list(PROBLEMS)
    return figures


if __name__ == "__main__":
    out = main()
    text = json.dumps(out, indent=1)
    (HERE / "verify_located.json").write_text(text, encoding="utf-8")
    print(text)
