"""Independent re-score of two_phase_v9n_place against two_phase_v9j on the held-out 26 (gpt-5.6-luna, high).

Exact scorer, as specified by the task:
  per module and run, a Counter of the listed "Asset RTL" names; the reference rows (manual_gt_neorv32.json, kept
  only when the element is a name in chain.closed_names(module)) are walked in order, and a row whose element still
  has a copy in the Counter consumes one and counts correct. listed = asset rows, findable = kept reference rows.
No API call. chain is imported only for closed_names and run_dir.

  python -B rescore.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ["PIO_INPUT_VERSION"] = "v1"
LAB = Path(r"E:\jobs\ff\test\Prepoison_subset\final\pio\lab")
sys.path.insert(0, str(LAB))
import chain  # noqa: E402  (closed_names, run_dir only)

GT = Path(r"E:\jobs\ff\test\Prepoison_subset\data\ground_truth\manual_gt_neorv32.json")
MODEL, EFFORT = "gpt-5.6-luna", "high"
BASE = "two_phase_v9j"
CHECK = ["two_phase_v9n_place"]
RUNS = (0, 1, 2)
BAR_R, BAR_P = 0.848, 0.569


def heldout() -> list[str]:
    d = LAB / "inputs" / "v1" / "heldout"
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def reference(m: str) -> list[str]:
    """Kept reference elements for module m, in file order."""
    names = {n for (_e, n) in chain.closed_names(m)}
    rows = json.loads(GT.read_text(encoding="utf-8"))["modules"][m]["assets"]
    return [r["element"] for r in rows if r["element"] in names]


def listed(version: str, rep: int, m: str) -> list[str] | None:
    p = chain.run_dir(version, MODEL, rep, EFFORT) / "assets" / f"{m}.json"
    if not p.exists():
        return None
    return [a["Asset RTL"] for a in json.loads(p.read_text(encoding="utf-8"))["Assets"]]


def score(ref: list[str], names: list[str]) -> tuple[int, int, int, list[bool]]:
    """(correct, listed, findable, hit flag per reference row)."""
    c = Counter(names)
    hits = []
    for e in ref:
        if c[e] > 0:
            c[e] -= 1
            hits.append(True)
        else:
            hits.append(False)
    return sum(hits), len(names), len(ref), hits


def selftest(mods: list[str]) -> None:
    # hand-read 2026-10-19 from the gpio reference rows and the two r0 asset files
    ref = reference("neorv32_gpio")
    assert ref == ["gpio_o", "irq_en", "irq_typ", "port_in", "port_out", "gpio_i", "irq_pend", "irq_clrn", "cpu_irq_o"], ref
    assert score(ref, listed(BASE, 0, "neorv32_gpio"))[:3] == (9, 11, 9)
    assert score(ref, listed("two_phase_v9n_place", 0, "neorv32_gpio"))[:3] == (8, 10, 9)
    # scorer semantics on synthetic rows: duplicates consume one copy each, order walked as given
    assert score(["a", "a", "b"], ["a", "c"])[:3] == (1, 2, 3)
    assert score(["a", "a"], ["a", "a", "a"])[:3] == (2, 3, 2)
    assert len(mods) == 26, len(mods)
    print("self-test PASS")


def run_table(version: str, mods: list[str]) -> dict:
    """{rep: {"correct", "listed", "findable", "hits": {(m, i, e): bool}, "names": {(m, name)}}} for runs with files."""
    out = {}
    for rep in RUNS:
        tot = {"correct": 0, "listed": 0, "findable": 0, "hits": {}, "names": set(), "modules": 0}
        for m in mods:
            names = listed(version, rep, m)
            if names is None:
                continue
            ref = reference(m)
            c, l, f, hits = score(ref, names)
            tot["correct"] += c
            tot["listed"] += l
            tot["findable"] += f
            tot["modules"] += 1
            for i, (e, h) in enumerate(zip(ref, hits)):
                tot["hits"][(m, i, e)] = h
            tot["names"] |= {(m, n) for n in names}
        if tot["modules"]:
            out[rep] = tot
    return out


def report(version: str, t: dict) -> dict:
    print(f"\n== {version}  (runs present: {', '.join(f'r{r}' for r in t)}; modules per run: "
          f"{', '.join(str(t[r]['modules']) for r in t)})")
    P = {"runs": {}}
    pc = pl = pf = 0
    for r, x in t.items():
        rec = x["correct"] / x["findable"] if x["findable"] else 0.0
        pre = x["correct"] / x["listed"] if x["listed"] else 0.0
        print(f"  r{r}: correct {x['correct']}  listed {x['listed']}  findable {x['findable']}  "
              f"recall {rec:.3f}  precision {pre:.3f}")
        P["runs"][f"r{r}"] = {"correct": x["correct"], "listed": x["listed"], "findable": x["findable"],
                              "recall": round(rec, 4), "precision": round(pre, 4)}
        pc += x["correct"]; pl += x["listed"]; pf += x["findable"]
    rec, pre = pc / pf, pc / pl
    print(f"  pooled: correct {pc}  listed {pl}  findable {pf}  recall {rec:.4f}  precision {pre:.4f}")
    P["pooled"] = {"correct": pc, "listed": pl, "findable": pf, "recall": round(rec, 4), "precision": round(pre, 4)}
    return P


def main() -> None:
    mods = heldout()
    selftest(mods)
    base = run_table(BASE, mods)
    out = {BASE: report(BASE, base)}
    base_all3 = {k for k, h in base[0]["hits"].items() if len(base) == 3 and all(base[r]["hits"].get(k) for r in base)}
    base_names = set().union(*(base[r]["names"] for r in base))
    for v in CHECK:
        t = run_table(v, mods)
        if not t:
            print(f"\n== {v}: no asset files in any run")
            out[v] = {"runs": {}, "pooled": None}
            continue
        P = report(v, t)
        rec, pre = P["pooled"]["recall"], P["pooled"]["precision"]
        print(f"  pooled recall >= {BAR_R}: {'YES' if rec >= BAR_R else 'NO'}   "
              f"pooled precision > {BAR_P}: {'YES' if pre > BAR_P else 'NO'}")
        P["recall_at_least_bar"] = rec >= BAR_R
        P["precision_above_bar"] = pre > BAR_P
        lost = sorted(k for k in base_all3 if sum(bool(t[r]["hits"].get(k)) for r in t) <= 1)
        print(f"  reference entries found in all 3 {BASE} runs but in <=1 {v} run: {len(lost)}")
        for m, i, e in lost:
            print(f"    {m}: {e}  (row {i}; found in {sum(bool(t[r]['hits'].get(k)) for r in t for k in [(m, i, e)])} run(s))")
        P["lost_vs_base"] = [{"module": m, "row": i, "element": e,
                              "found_in_runs": sum(bool(t[r]["hits"].get((m, i, e))) for r in t)} for m, i, e in lost]
        cnt = Counter(n for r in t for n in t[r]["names"])
        new = sorted(n for n, c in cnt.items() if c >= 2 and n not in base_names)
        print(f"  names listed in >=2 {v} runs that {BASE} never lists: {len(new)}")
        for m, n in new:
            print(f"    {m}: {n}  (listed in {cnt[(m, n)]} run(s))")
        P["new_vs_base"] = [{"module": m, "name": n, "listed_in_runs": cnt[(m, n)]} for m, n in new]
        out[v] = P
    (Path(__file__).parent / "rescore_result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
