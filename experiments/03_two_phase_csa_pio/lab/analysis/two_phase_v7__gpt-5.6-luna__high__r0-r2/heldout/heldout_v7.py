"""two_phase_v7 on the 26 held-out modules (runs r0-r2) next to v7 on the 15 tuning modules. Read-only on stored files;
writes heldout_v7.json.

Scorer: compare_v8.py's (exact names, each reference entry used once; findable = reference names present in the
module's closed set: 109 per tuning run, 187 per held-out run). Its self-test runs first: on the tuning modules it
reproduces v7's 92/89/86 correct of 146/158/131 listed and equals compare_condensed.score() on every module and run.
Reported per split: completeness (assets files, pending requests, replies moved to _schema_failed, failed calls),
format slips (missing walks, asset rows written inside points, asset rows without a name), per-run and pooled
precision (correct / listed) and recall (correct / findable), per-module counts for the held-out split, and the
elements found in all, some or none of the 3 runs.

  python heldout_v7.py
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402

V, MODEL, EFF, REPS = "two_phase_v7", "gpt-5.6-luna", "high", (0, 1, 2)


def completeness(mods):
    out = {}
    for r in REPS:
        d = CH.run_dir(V, MODEL, r, EFF)
        failed = 0
        if (d / "_failed_calls.jsonl").exists():
            failed = sum(1 for l in (d / "_failed_calls.jsonl").read_text(encoding="utf-8").splitlines()
                         if l.strip() and json.loads(l).get("module") in mods)
        out[f"r{r}"] = {"assets files": sum((d / "assets" / f"{m}.json").exists() for m in mods),
                        "phase 1 / phase 2 replies": (sum((d / "phase1" / f"{m}.json").exists() for m in mods),
                                                      sum((d / "phase2" / f"{m}.json").exists() for m in mods)),
                        "pending": len(list((d / "_pending").glob("*.json"))) if (d / "_pending").exists() else 0,
                        "replies moved to _schema_failed": sum((d / "_schema_failed" / f"phase{p}" / f"{m}.json").exists() for m in mods for p in (1, 2)),
                        "failed calls": failed}
    return out


def slips(mods):
    out = {}
    for r in REPS:
        d = CH.run_dir(V, MODEL, r, EFF)
        c = Counter()
        for m in mods:
            p1 = K.parse_json(json.loads((d / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            p2 = K.parse_json(json.loads((d / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            ids = [x.get("Concept ID") for x in p1.get("Conceptual Assets", []) if isinstance(x, dict)]
            walks = [w for w in (p2.get("Concept Walks") or []) if isinstance(w, dict)]
            have = {w.get("Concept ID") for w in walks}
            c["concepts"] += len(ids)
            c["missing walks"] += sum(1 for i in ids if i not in have)
            for w in walks:
                c["asset rows inside points"] += sum(len(p.get("Assets") or []) for p in (w.get("Points") or [])
                                                     if isinstance(p, dict) and isinstance(p.get("Assets"), list))
                c["asset rows without a name"] += sum(1 for a in (w.get("Assets") or []) if isinstance(a, dict) and not a.get("Asset RTL"))
        out[f"r{r}"] = dict(c)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tun, held = K.gt_modules()["tuning"], K.gt_modules()["heldout"]
    ref = C8.refs(sorted(set(tun) | set(held)))
    ok = C8.selftest(ref)
    print("self-test (compare_v8 scorer: v7 tuning 92/89/86 of 146/158/131; equal to compare_condensed.score):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    rep = {}
    for split, mods in (("tuning", tun), ("held-out", held)):
        comp, sl = completeness(mods), slips(mods)
        x = C8.runs(V, mods, ref)
        F = sum(len(ref[m]) for m in mods)
        T, L = sum(y["correct"] for y in x.values()), sum(y["listed"] for y in x.values())
        found = Counter(e for y in x.values() for e in y["cset"])
        n_el = F
        allr = sum(1 for n in found.values() if n == 3)
        some = sum(1 for n in found.values() if n in (1, 2))
        rep[split] = {
            "modules": len(mods), "findable per run": F,
            "completeness": comp, "format slips": sl,
            "per run (correct, listed, precision, recall)": {f"r{r}": (y["correct"], y["listed"], round(y["correct"] / y["listed"], 3), round(y["correct"] / F, 3)) for r, y in x.items()},
            "pooled precision": f"{T}/{L} = {T / L:.3f}", "pooled recall": f"{T}/{3 * F} = {T / (3 * F):.3f}",
            "false positives per run": [y["listed"] - y["correct"] for y in x.values()],
            "elements found in 3 / 1-2 / 0 runs": [allr, some, n_el - allr - some],
            "per module (correct of findable, listed) r0/r1/r2": {m.replace("neorv32_", ""): [f"{C8.score(V, r, m, ref)[1]}/{len(ref[m])}, {C8.score(V, r, m, ref)[0]}" for r in REPS] for m in mods},
        }
        print(f"\n== {split}: {len(mods)} modules, {F} findable per run")
        print("  completeness:", json.dumps(comp))
        print("  format slips:", json.dumps(sl))
        print("  per run (correct, listed, P, R):", rep[split]["per run (correct, listed, precision, recall)"])
        print(f"  pooled precision {rep[split]['pooled precision']}; pooled recall {rep[split]['pooled recall']}; false positives per run {rep[split]['false positives per run']}")
        print(f"  elements found in all 3 runs / 1-2 runs / no run: {rep[split]['elements found in 3 / 1-2 / 0 runs']} (of {n_el})")
    (HERE / "heldout_v7.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
