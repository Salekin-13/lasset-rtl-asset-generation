"""Prompt versions (two_phase_v1, v2, v4a, v5, v6, v7, v8; gpt-5.6-luna, high, runs r0-r2, inputs v1) on the 15 tuning
modules and the 26 held-out modules: how much each version drops from tuning to held-out. Read-only on stored runs;
writes compare_versions.json.

Exact scorer of compare_v8.py (names equal, each reference entry used once; findable = reference names in the module's
closed set: 109 per run on the tuning modules, 187 on the held-out ones). Precision = correct / listed, recall =
correct / findable; pooled = summed over the 3 runs. TP = correct finds, FP = listed - correct, FN = findable - correct.
Groups: tuning (15), held-out (26), and the held-out split by locate_degradation.py into the 12 modules that cause
v7's drop and the other 14. The 12 were picked from v7's own results, so v7 looks worst on them by construction; for
the other versions they are an ordinary subset.

Checks before anything is reported:
  - every version has all 41 modules in both phases and an assets file, for r0-r2, nothing pending;
  - every stored reply of a version was asked with one system prompt per phase (tuning and held-out alike), and that
    prompt is the version's current prompt file (check_lab_prompt.system);
  - the scorer's self-test (compare_v8.selftest) and, on the tuning modules, the per-run correct / listed counts in
    EXPERIMENT_LOG.md's version table for v1, v2, v4a, v5, v6 and v7 (written by earlier scripts).
A version whose held-out run is not complete (for example one still running) is left out with a message.

  python compare_versions.py [extra versions, e.g. two_phase_v5]
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import check_lab_prompt as C  # noqa: E402
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402

MODEL, EFF, REPS = "gpt-5.6-luna", "high", (0, 1, 2)
VERS = ["two_phase_v1", "two_phase_v2", "two_phase_v4a", "two_phase_v5", "two_phase_v6", "two_phase_v7", "two_phase_v8"]
LOGGED = {  # EXPERIMENT_LOG.md version table, tuning modules: (correct, listed) per run
    "two_phase_v1": [(88, 480), (87, 481), (88, 510)], "two_phase_v2": [(85, 425), (85, 349), (87, 354)],
    "two_phase_v4a": [(94, 320), (84, 295), (94, 293)], "two_phase_v5": [(91, 246), (81, 216), (87, 214)],
    "two_phase_v6": [(86, 143), (83, 134), (86, 134)],
    "two_phase_v7": [(92, 146), (89, 158), (86, 131)]}
LOC = json.loads((LAB / "analysis" / "two_phase_v7__gpt-5.6-luna__high__r0-r2" / "heldout" / "locate_degradation.json").read_text(encoding="utf-8"))


def short(v):
    return v.replace("two_phase_", "")


def groups_and_ref():
    g = K.gt_modules()
    resp = ["neorv32_" + m for m in LOC["responsible modules (union)"]]
    groups = {"tuning": g["tuning"], "held-out": g["heldout"], "held-out: the 12": resp,
              "held-out: other 14": [m for m in g["heldout"] if m not in resp]}
    return groups, C8.refs(sorted(set(g["tuning"]) | set(g["heldout"])))


def complete(v, mods) -> list[str]:
    """Problems that make version v unreadable on mods (empty list = complete and one prompt per phase)."""
    probs = []
    sha = {ph: CH.sha12(C.system(v, ph)) for ph in (1, 2)}
    seen = {1: set(), 2: set()}
    for r in REPS:
        d = CH.run_dir(v, MODEL, r, EFF)
        for m in mods:
            for ph in (1, 2):
                f = d / f"phase{ph}" / f"{m}.json"
                if not f.exists():
                    probs.append(f"r{r}: no phase {ph} reply for {m}")
                    continue
                seen[ph].add(json.loads(f.read_text(encoding="utf-8"))["system sha"])
            if not (d / "assets" / f"{m}.json").exists():
                probs.append(f"r{r}: no assets file for {m}")
        if (d / "_pending").exists() and any((d / "_pending").iterdir()):
            probs.append(f"r{r}: requests still pending")
    for ph in (1, 2):
        if seen[ph] and seen[ph] != {sha[ph]}:
            probs.append(f"phase {ph}: stored system shas {sorted(seen[ph])}, prompt file {sha[ph]}")
    return probs


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, ref = groups_and_ref()
    allm = groups["tuning"] + groups["held-out"]
    vers = []
    for v in VERS + [a for a in sys.argv[1:] if a not in VERS]:
        p = complete(v, allm)
        if p:
            print(f"{short(v)}: left out ({len(p)} problems; first: {p[0]})")
            if v in VERS:
                sys.exit("a base version is incomplete: nothing reported")
        else:
            vers.append(v)
    ok = C8.selftest(ref)
    for v, want in LOGGED.items():
        x = C8.runs(v, groups["tuning"], ref)
        got = [(x[r]["correct"], x[r]["listed"]) for r in REPS]
        if got != want:
            print(f"  {short(v)} tuning: scorer {got}, EXPERIMENT_LOG {want}")
            ok = False
    print("self-checks (complete runs, one prompt per version = current file, scorer self-test, logged tuning counts):",
          "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    out = {"groups": {k: [m.replace("neorv32_", "") for m in v] for k, v in groups.items()}, "versions": {}, "modules": {}}
    print("\npooled over r0-r2: TP / FP / FN, precision P, recall R")
    for k, mods in groups.items():
        print(f"  {k} ({len(mods)} modules, {sum(len(ref[m]) for m in mods)} findable per run)")
    for v in vers:
        row = {}
        for k, mods in groups.items():
            x = C8.runs(v, mods, ref)
            F = sum(len(ref[m]) for m in mods)
            T, L = sum(y["correct"] for y in x.values()), sum(y["listed"] for y in x.values())
            row[k] = {"findable per run": F, "per run (correct, listed)": [(x[r]["correct"], x[r]["listed"]) for r in REPS],
                      "precision per run": [round(x[r]["correct"] / x[r]["listed"], 3) for r in REPS],
                      "recall per run": [round(x[r]["correct"] / F, 3) for r in REPS],
                      "TP": T, "FP": L - T, "FN": 3 * F - T,
                      "pooled precision": [T, L, round(T / L, 3)], "pooled recall": [T, 3 * F, round(T / (3 * F), 3)]}
        for k in ("held-out", "held-out: the 12", "held-out: other 14"):
            row[f"change {k} minus tuning"] = {"precision": round(row[k]["pooled precision"][2] - row["tuning"]["pooled precision"][2], 3),
                                               "recall": round(row[k]["pooled recall"][2] - row["tuning"]["pooled recall"][2], 3)}
        out["versions"][short(v)] = row
    for k in groups:
        print(f"\n{k}:")
        for v in vers:
            z = out["versions"][short(v)][k]
            print(f"  {short(v):5s} TP {z['TP']:4d}  FP {z['FP']:4d}  FN {z['FN']:4d} | P {z['pooled precision'][2]:.3f} "
                  f"(runs {z['precision per run']})  R {z['pooled recall'][2]:.3f} (runs {z['recall per run']})")
    print("\nchange, held-out minus tuning (pooled):")
    for v in vers:
        r = out["versions"][short(v)]
        print(f"  {short(v):5s} " + "   ".join(f"{k}: P {r[f'change {k} minus tuning']['precision']:+.3f} R {r[f'change {k} minus tuning']['recall']:+.3f}"
                                         for k in ("held-out", "held-out: the 12", "held-out: other 14")))
    print("\nper held-out module, pooled over 3 runs: TP / FP / FN")
    print(f"{'module':22s}{'find':>5s}" + "".join(f"{short(v):>15s}" for v in vers))
    for m in groups["held-out"]:
        f = len(ref[m])
        cells, mrow = [], {}
        for v in vers:
            s = [C8.score(v, r, m, ref) for r in REPS]
            T, L = sum(z[1] for z in s), sum(z[0] for z in s)
            mrow[short(v)] = {"TP": T, "FP": L - T, "FN": 3 * f - T}
            cells.append(f"{T:3d}/{L - T:3d}/{3 * f - T:3d}")
        out["modules"][m.replace("neorv32_", "")] = mrow
        mark = "*" if m in groups["held-out: the 12"] else " "
        print(f"{mark}{m.replace('neorv32_', ''):21s}{f:5d}" + "".join(f"{c:>15s}" for c in cells))
    (HERE / "compare_versions.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\n* = one of the 12 modules that cause v7's drop (locate_degradation.py). written compare_versions.json")


if __name__ == "__main__":
    main()
