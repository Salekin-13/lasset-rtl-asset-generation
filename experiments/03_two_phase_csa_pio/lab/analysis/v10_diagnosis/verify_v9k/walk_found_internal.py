"""Re-derive the "walk-found internal primaries" reading for two_phase_v9k and two_phase_v9j, per run.

Definitions (as given for this check):
  listed rows    runs/<version>__v1/gpt-5.6-luna__high/r<k>/assets/<module>.json ["Assets"], field "Asset RTL"
  concepts       runs/.../r<k>/phase1/<module>.json ["reply"]["conceptual assets"]: entries with "id",
                 "enters through" [names], "leaves through" [names], "held lines" [ints]
  reference      data/ground_truth/manual_gt_neorv32.json ["modules"][module]["assets"][*]["element"], kept only
                 when the element is a name in chain.closed_names(module)
  exact scorer   per module and run: Counter of listed names; reference rows walked in order, a row whose element
                 still has a copy consumes one and counts correct. listed = asset rows, findable = reference rows.
                 Row-level correctness: the first (consumed) copies of a name in list order are correct.
  ANCHORED       for at least one concept id of the row: the name is in that concept's "enters through" or
                 "leaves through", or the name's assignment lines intersect its "held lines".
  assignment     union of "lines" of the name's counterpart entries under "gets value from", "decided by",
                 "reset by", "clocked by" in chain.closed_names(module); lookup (row Entity, name) first, then any
                 entity with that name (union over those).
  INTERNAL       the part of the name before the first "." is not a port: its closed-set record has no "direction".

Report: per version and run, rows that are INTERNAL and NOT ANCHORED, split correct / false, plus pooled totals,
for all 41 modules and for the four groups. Also the exact scorer per run (as a cross-check against stored readings).

  python -B walk_found_internal.py          (writes walk_found_internal.json next to this file)
No API calls. Reads chain.py and labkit.py only.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]                      # verify_v9k -> v10_diagnosis -> analysis -> lab
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
import chain  # noqa: E402

GT = ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json"
RUNS = LAB / "runs"
MODEL = "gpt-5.6-luna__high"
VERSIONS = ("two_phase_v9k", "two_phase_v9j")
REPS = (0, 1, 2)
ASSIGN_KEYS = ("gets value from", "decided by", "reset by", "clocked by")

_CN = {}


def closed(m: str) -> dict:
    if m not in _CN:
        _CN[m] = chain.closed_names(m)
    return _CN[m]


# ------------------------------------------------------------------------------------------ reference / groups ---
def reference() -> dict[str, list[str]]:
    gt = json.loads(GT.read_text(encoding="utf-8"))["modules"]
    out = {}
    for m, rec in gt.items():
        names = {k[1] for k in closed(m)}
        out[m] = [r["element"] for r in rec["assets"] if r["element"] in names]
    return out


def groups(ref: dict) -> dict[str, list[str]]:
    tuning_dirs = sorted(d.name for d in (chain.INPUTS / "tuning").iterdir() if d.is_dir())
    heldout_dirs = sorted(d.name for d in (chain.INPUTS / "heldout").iterdir() if d.is_dir())
    sp = json.loads((LAB / "splits" / "tuning_v2.json").read_text(encoding="utf-8"))
    return {
        "tuning 15": [m for m in tuning_dirs if ref.get(m)],
        "held-out 26": heldout_dirs,
        "tuning_v2": list(sp["tuning"]),
        "heldout_v2": list(sp["heldout"]),
    }


# ------------------------------------------------------------------------------------------------- scorer ---
def score(listed: list[str], ref: list[str]) -> tuple[int, int, int, list[bool]]:
    """(correct, listed, findable, per-row correctness in list order)."""
    pool = Counter(listed)
    consumed = Counter()
    for e in ref:
        if pool[e] > 0:
            pool[e] -= 1
            consumed[e] += 1
    correct = sum(consumed.values())
    seen = Counter()
    rows = []
    for n in listed:
        rows.append(seen[n] < consumed[n])
        seen[n] += 1
    return correct, len(listed), len(ref), rows


# ------------------------------------------------------------------------------------------ anchored / internal ---
def _records(cn: dict, entity: str, name: str) -> list[dict]:
    r = cn.get((entity, name))
    if r is not None:
        return [r]
    return [v for (e, n), v in cn.items() if n == name]


def assignment_lines(cn: dict, entity: str, name: str) -> set[int]:
    lines = set()
    for rec in _records(cn, entity, name):
        for k in ASSIGN_KEYS:
            for c in rec.get("counterparts", {}).get(k, []):
                lines |= {int(x) for x in c.get("lines", [])}
    return lines


def is_internal(cn: dict, entity: str, name: str) -> bool | None:
    """True = top-level element is not a port; False = it is a port; None = top-level element not in the closed set."""
    top = name.split(".", 1)[0]
    recs = _records(cn, entity, top)
    if not recs:
        return None
    return all("direction" not in r for r in recs)


def is_anchored(row: dict, concepts: dict[str, dict], cn: dict) -> bool:
    name = row["Asset RTL"]
    al = None
    for cid in row.get("Concepts", []):
        c = concepts.get(cid)
        if c is None:
            continue
        if name in chain.as_list(c.get("enters through")) or name in chain.as_list(c.get("leaves through")):
            return True
        if al is None:
            al = assignment_lines(cn, row["Entity"], name)
        if al & {int(x) for x in chain.as_list(c.get("held lines"))}:
            return True
    return False


# -------------------------------------------------------------------------------------------------- per module ---
def module_rows(version: str, rep: int, m: str, ref_elems: list[str]) -> dict:
    d = RUNS / f"{version}__v1" / MODEL / f"r{rep}"
    rows = json.loads((d / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
    concepts = {c["id"]: c for c in json.loads((d / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["reply"]["conceptual assets"]}
    cn = closed(m)
    correct, listed, findable, row_ok = score([x["Asset RTL"] for x in rows], ref_elems)
    out = []
    for x, ok in zip(rows, row_ok):
        internal = is_internal(cn, x["Entity"], x["Asset RTL"])
        out.append({"entity": x["Entity"], "name": x["Asset RTL"], "concepts": list(x.get("Concepts", [])),
                    "correct": ok, "internal": internal, "anchored": is_anchored(x, concepts, cn),
                    "pair_in_closed_set": (x["Entity"], x["Asset RTL"]) in cn})
    return {"correct": correct, "listed": listed, "findable": findable, "rows": out}


def tally(rows: list[dict]) -> dict:
    sel = [r for r in rows if r["internal"] is True and not r["anchored"]]
    return {"internal_not_anchored": len(sel), "correct": sum(r["correct"] for r in sel),
            "false": sum(not r["correct"] for r in sel), "internal": sum(r["internal"] is True for r in rows),
            "internal_unknown": sum(r["internal"] is None for r in rows), "rows": len(rows)}


# ---------------------------------------------------------------------------------------------------- self-test ---
def selftest(ref: dict) -> list[str]:
    """Hand-read from the raw files before this script was run (see the session log):
    neorv32_uart, two_phase_v9j r0: 13 rows; internal rows 0,2,3,4,7,10; rows 0/2/3 anchored by held lines
    179/182/183; rows 4 (tx_engine.sreg), 7 (rx_engine.sreg), 10 (rx_engine.over) internal and not anchored, none
    in the reference -> 3 (0 correct, 3 false); scorer 10 correct / 13 listed / 10 findable.
    neorv32_wdt, two_phase_v9k r2: figures filled in from the second hand read (HAND_WDT below)."""
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")

    r = module_rows("two_phase_v9j", 0, "neorv32_uart", ref["neorv32_uart"])
    t = tally(r["rows"])
    check("uart scorer", (r["correct"], r["listed"], r["findable"]), (10, 13, 10))
    check("uart internal", t["internal"], 6)
    check("uart internal-not-anchored", (t["internal_not_anchored"], t["correct"], t["false"]), (3, 0, 3))
    check("uart which rows", sorted(x["name"] for x in r["rows"] if x["internal"] and not x["anchored"]),
          sorted(["tx_engine.sreg", "rx_engine.sreg", "rx_engine.over"]))
    if HAND_WDT is not None:
        r = module_rows("two_phase_v9k", 2, "neorv32_wdt", ref["neorv32_wdt"])
        t = tally(r["rows"])
        check("wdt scorer", (r["correct"], r["listed"], r["findable"]), HAND_WDT["scorer"])
        check("wdt internal", t["internal"], HAND_WDT["internal"])
        check("wdt internal-not-anchored", (t["internal_not_anchored"], t["correct"], t["false"]), HAND_WDT["ina"])
        check("wdt which rows", sorted(x["name"] for x in r["rows"] if x["internal"] and not x["anchored"]),
              sorted(HAND_WDT["names"]))
    return fails


# Second hand read (neorv32_wdt, two_phase_v9k r2, raw files printed before the script ran): 8 rows; internal rows
# 0,2,3,4,5,7; rows 0/2/3/5 anchored by held lines 94/95/97/144; row 4 reset_wdt (held 103, assignment lines end at
# 102) and row 7 reset_cause (held 169/172/174/176 vs 168/170/171/173/175) internal and not anchored; both are
# reference elements listed once -> 2 correct / 0 false; scorer: 7 of 8 reference elements listed (cnt missing),
# 8 listed rows -> 7 / 8 / 8.
HAND_WDT = {"scorer": (7, 8, 8), "internal": 6, "ina": (2, 2, 0), "names": ["reset_wdt", "reset_cause"]}


# --------------------------------------------------------------------------------------------------------- main ---
def main() -> int:
    ref = reference()
    grp = groups(ref)
    all41 = sorted(set(grp["tuning 15"]) | set(grp["held-out 26"]))
    fails = selftest(ref)
    if fails:
        print("SELF-TEST FAILED; nothing reported")
        for f in fails:
            print("  " + f)
        return 1
    print("self-test PASS (neorv32_uart v9j r0" + (", neorv32_wdt v9k r2" if HAND_WDT else "") + ")")
    print(f"modules: all 41 = {len(all41)}; " + "; ".join(f"{g} = {len(ms)}" for g, ms in grp.items()))

    result = {"versions": {}, "groups": {g: ms for g, ms in grp.items()}, "all41": all41}
    for ver in VERSIONS:
        result["versions"][ver] = {}
        for rep in REPS:
            per_mod = {m: module_rows(ver, rep, m, ref[m]) for m in all41}
            result["versions"][ver][f"r{rep}"] = per_mod
    (HERE / "walk_found_internal.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    def block(ver: str, rep: int, mods: list[str]) -> dict:
        per_mod = result["versions"][ver][f"r{rep}"]
        rows = [r for m in mods for r in per_mod[m]["rows"]]
        t = tally(rows)
        t["scorer"] = {"correct": sum(per_mod[m]["correct"] for m in mods),
                       "listed": sum(per_mod[m]["listed"] for m in mods),
                       "findable": sum(per_mod[m]["findable"] for m in mods)}
        t["pair_not_in_closed_set"] = sum(not r["pair_in_closed_set"] for r in rows)
        return t

    summary = {}
    for gname, mods in [("all 41", all41)] + list(grp.items()):
        print(f"\n=== group: {gname} ({len(mods)} modules) ===")
        print(f"{'version':16s} run  rows  internal  internal&not-anchored  correct  false   | scorer correct/listed/findable")
        for ver in VERSIONS:
            pooled = Counter()
            for rep in REPS:
                t = block(ver, rep, mods)
                summary[(gname, ver, f"r{rep}")] = t
                for k in ("rows", "internal", "internal_not_anchored", "correct", "false", "internal_unknown"):
                    pooled[k] += t[k]
                for k in ("correct", "listed", "findable"):
                    pooled["s_" + k] += t["scorer"][k]
                sc = t["scorer"]
                print(f"{ver:16s} r{rep}   {t['rows']:4d}  {t['internal']:8d}  {t['internal_not_anchored']:21d}  "
                      f"{t['correct']:7d}  {t['false']:5d}   | {sc['correct']}/{sc['listed']}/{sc['findable']}"
                      f"   P={sc['correct']/sc['listed']:.3f} R={sc['correct']/sc['findable']:.3f}")
            print(f"{ver:16s} pooled {pooled['rows']:4d}  {pooled['internal']:8d}  {pooled['internal_not_anchored']:21d}  "
                  f"{pooled['correct']:7d}  {pooled['false']:5d}   | {pooled['s_correct']}/{pooled['s_listed']}/{pooled['s_findable']}"
                  f"   P={pooled['s_correct']/pooled['s_listed']:.3f} R={pooled['s_correct']/pooled['s_findable']:.3f}"
                  + (f"   (internal unknown: {pooled['internal_unknown']})" if pooled["internal_unknown"] else ""))
            summary[(gname, ver, "pooled")] = dict(pooled)
    # loose ends worth stating
    unknown = [(ver, rep, m, r["name"]) for ver in VERSIONS for rep in REPS for m in all41
               for r in result["versions"][ver][f"r{rep}"][m]["rows"] if r["internal"] is None]
    notpair = [(ver, rep, m, r["entity"], r["name"]) for ver in VERSIONS for rep in REPS for m in all41
               for r in result["versions"][ver][f"r{rep}"][m]["rows"] if not r["pair_in_closed_set"]]
    print(f"\nrows whose top-level element is not in the closed set (internal unknown): {len(unknown)} {unknown[:10]}")
    print(f"rows whose (Entity, name) pair is not in the closed set (name looked up in any entity): {len(notpair)} {notpair[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
