"""Per-module scoring record of one two-phase version, from its stored replies: one CSV row per (run, module, element name)
with the reference count, the listed count, hits, misses and false positives, so a reader can see every false positive
and every miss without an API call. Read-only on the runs. Same counting as compare_v8.score: names equal, each reference
entry used once, findable = reference entries whose name is in the module's closed set. A reference entry whose name is
not in the closed set gets a row with findable = 0; it is outside the scorer's recall denominator and counts no miss.

Columns: version, run, split, module, element, findable, reference_count, listed_count, hits, misses, false_positives,
entity, objective. entity and objective come from the listed rows of the converted asset list (`assets/<module>.json`);
several values are joined with "; ".

Self-test (runs first; nothing is written if it fails): per module and run, hits and listed equal compare_v8.score;
per split and run, the totals equal the saved rows of score_versions.json.

  python score_records.py                      (two_phase_p1o_first)
  python score_records.py two_phase_v7         (another version with stored runs)
Writes score_records_<version>.csv beside this script.
"""
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path


def _root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "FINAL_NOTEBOOK.ipynb").exists():
            return p
    raise SystemExit("run this script from inside the repository")


ROOT = _root()
LAB = ROOT / "experiments" / "03_two_phase_csa_pio" / "lab"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8")
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402
import chain as CH  # noqa: E402

MODEL, EFF = "gpt-5.6-luna", "high"
COLS = ["version", "run", "split", "module", "element", "findable", "reference_count", "listed_count", "hits", "misses",
        "false_positives", "entity", "objective"]


def all_refs(mods: list[str]) -> dict[str, list[str]]:
    """Every reference entry name per module, findable or not, in the reference's order."""
    import eval_assets as ea
    with CH.at_root():
        gt = ea.load_refs()["gt"]
    return {m: [n for n, _ in gt[m]] for m in mods}


def listed_rows(version: str, rep: int, module: str):
    f = CH.run_dir(version, MODEL, rep, EFF) / "assets" / f"{module}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))["Assets"]


def module_rows(version: str, rep: int, split: str, module: str, ref_all: list[str], ref_findable: list[str]):
    rows = listed_rows(version, rep, module)
    if rows is None:
        return None
    names = [x["Asset RTL"] for x in rows]
    listed, ref_c, ref_f = Counter(names), Counter(ref_all), Counter(ref_findable)
    detail: dict[str, dict[str, list]] = {}
    for x in rows:
        d = detail.setdefault(x["Asset RTL"], {"entity": [], "objective": []})
        for k, key in (("entity", "Entity"), ("objective", "Security Objective")):
            v = str(x.get(key, "") or "")
            if v and v not in d[k]:
                d[k].append(v)
    out = []
    for n in sorted(set(ref_all) | set(names)):
        hits = min(ref_f[n], listed[n])
        out.append({
            "version": version, "run": rep, "split": split, "module": module, "element": n,
            "findable": int(ref_f[n] > 0) if ref_c[n] else "",
            "reference_count": ref_c[n], "listed_count": listed[n], "hits": hits,
            "misses": ref_f[n] - hits, "false_positives": listed[n] - hits,
            "entity": "; ".join(detail.get(n, {}).get("entity", [])),
            "objective": "; ".join(detail.get(n, {}).get("objective", [])),
        })
    return out


def main(version: str) -> int:
    g = K.gt_modules()
    mods = g["tuning"] + g["heldout"]
    split_of = {m: "tuning" for m in g["tuning"]} | {m: "heldout" for m in g["heldout"]}
    ref_f = C8.refs(mods)
    ref_all = all_refs(mods)
    saved = json.loads((HERE / "score_versions.json").read_text(encoding="utf-8")).get(version, {})

    rows, ok, notes = [], True, []
    reps = [r for r in range(0, 6) if CH.run_dir(version, MODEL, r, EFF).exists()]
    if not reps:
        print(f"no stored runs for {version} under {CH.run_dir(version, MODEL, 0, EFF).parent}")
        return 1
    for r in reps:
        run_rows, complete = [], True
        for m in mods:
            mr = module_rows(version, r, split_of[m], m, ref_all[m], ref_f[m])
            if mr is None:
                complete = False
                notes.append(f"r{r}: {m} has no asset list; run skipped")
                break
            # self-test 1: the module's hits and listed equal the lab's scorer
            s = C8.score(version, r, m, ref_f)
            got = (sum(x["listed_count"] for x in mr), sum(x["hits"] for x in mr))
            if got != (s[0], s[1]):
                ok = False
                notes.append(f"self-test FAIL r{r} {m}: records {got} vs compare_v8 {(s[0], s[1])}")
            run_rows += mr
        if not complete:
            continue
        # self-test 2: the per-run totals equal the saved rows (when the saved file has this run)
        for split in ("tuning", "heldout"):
            T = sum(x["hits"] for x in run_rows if x["split"] == split)
            L = sum(x["listed_count"] for x in run_rows if x["split"] == split)
            F = sum(x["reference_count"] for x in run_rows if x["split"] == split and x["findable"] == 1)
            srow = saved.get(split)
            if srow and r in srow["runs"]:
                exp = tuple(srow["per_run"][srow["runs"].index(r)])
                if (T, L) != exp or F != srow["findable"]:
                    ok = False
                    notes.append(f"self-test FAIL r{r} {split}: records {(T, L)} findable {F} vs saved {exp} / {srow['findable']}")
            print(f"r{r} {split:8s} correct {T:4d} / listed {L:4d}, findable {F}")
        rows += run_rows

    for n in notes:
        print(n)
    print("self-test:", "PASS" if ok else "FAIL")
    if not ok or not rows:
        print("nothing written")
        return 1
    out = HERE / f"score_records_{version}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    fp = sum(x["false_positives"] for x in rows)
    miss = sum(x["misses"] for x in rows)
    print(f"wrote {out.relative_to(ROOT)}: {len(rows)} rows, {len(reps)} runs; false positives {fp}, misses {miss} summed over the runs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "two_phase_p1o_first"))
