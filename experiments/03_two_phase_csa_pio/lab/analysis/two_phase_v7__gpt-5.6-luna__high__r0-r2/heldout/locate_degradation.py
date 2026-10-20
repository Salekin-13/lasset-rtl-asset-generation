"""Which held-out modules cause v7's drop from tuning to held-out? (two_phase_v7, gpt-5.6-luna, high, r0-r2.)

Per held-out module, pooled over the 3 runs (exact scorer of compare_v8.py; self-test first):
  excess false positives = FP - correct x (1 - P_t) / P_t, with P_t = v7's pooled tuning precision 267/435. Removing
      exactly this many false positives from every module would lift held-out precision to P_t (keeping the correct
      finds); a negative value means the module is already at or above tuning precision.
  excess misses = missed - findable x 3 x (1 - R_t), with R_t = v7's pooled tuning recall 267/327. Recovering exactly
      this many would lift held-out recall to R_t.
  Per run as well: in how many of the 3 runs the module's excess is positive (a module whose excess shows in one run
  only may be noise).
Responsible modules: ranked by excess, the smallest set covering at least 80% of the total positive excess, on either
metric, and positive in at least 2 of the 3 runs. (80% is a chosen cut, stated as such.) Then the held-out remainder
without them is scored, to check the rest is near tuning level.
Writes locate_degradation.json.   python locate_degradation.py
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v8__gpt-5.6-luna__high__r0-r2"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import labkit as K  # noqa: E402
import compare_v8 as C8  # noqa: E402

V, REPS, COVER, MIN_RUNS = "two_phase_v7", (0, 1, 2), 0.80, 2


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tun, held = K.gt_modules()["tuning"], K.gt_modules()["heldout"]
    ref = C8.refs(sorted(set(tun) | set(held)))
    if not C8.selftest(ref):
        sys.exit("self-test failed")
    print("self-test (v7 tuning 92/89/86 of 146/158/131): PASS")
    t = C8.runs(V, tun, ref)
    Tt, Lt, Ft = sum(y["correct"] for y in t.values()), sum(y["listed"] for y in t.values()), 3 * sum(len(ref[m]) for m in tun)
    Pt, Rt = Tt / Lt, Tt / Ft
    print(f"tuning: precision {Tt}/{Lt} = {Pt:.3f}, recall {Tt}/{Ft} = {Rt:.3f}")
    rows = {}
    for m in held:
        per = [C8.score(V, r, m, ref) for r in REPS]
        f = len(ref[m])
        c = [p[1] for p in per]
        l = [p[0] for p in per]
        fp = [li - ci for li, ci in zip(l, c)]
        ms = [f - ci for ci in c]
        efp_r = [fp[i] - c[i] * (1 - Pt) / Pt for i in range(3)]
        ems_r = [ms[i] - f * (1 - Rt) for i in range(3)]
        rows[m] = {"findable per run": f, "correct": sum(c), "listed": sum(l), "false positives": sum(fp), "missed": sum(ms),
                   "precision": round(sum(c) / sum(l), 3) if sum(l) else None, "recall": round(sum(c) / (3 * f), 3) if f else None,
                   "excess false positives": round(sum(efp_r), 1), "excess misses": round(sum(ems_r), 1),
                   "runs with excess FP": sum(x > 0 for x in efp_r), "runs with excess misses": sum(x > 0 for x in ems_r),
                   "CPU sub-unit (name starts cpu_)": m.startswith("neorv32_cpu_")}
    out = {"tuning precision": f"{Tt}/{Lt}", "tuning recall": f"{Tt}/{Ft}", "modules": rows, "responsible": {}}
    for key, runs_key in (("excess false positives", "runs with excess FP"), ("excess misses", "runs with excess misses")):
        pos = sorted(((m, r[key]) for m, r in rows.items() if r[key] > 0), key=lambda x: -x[1])
        total = sum(v for _, v in pos)
        chosen, acc = [], 0.0
        for m, v in pos:
            if acc >= COVER * total:
                break
            chosen.append(m)
            acc += v
        kept = [m for m in chosen if rows[m][runs_key] >= MIN_RUNS]
        out["responsible"][key] = {"total positive excess": round(total, 1), "covered by the ranked set": round(acc, 1),
                                   "ranked set (80% cover)": [m.replace("neorv32_", "") for m in chosen],
                                   "kept (positive in 2+ runs)": [m.replace("neorv32_", "") for m in kept],
                                   "dropped as one-run": [m.replace("neorv32_", "") for m in chosen if m not in kept]}
        print(f"\n{key}: total positive {total:.1f} over {len(pos)} modules; 80% covered by {len(chosen)} modules ({acc:.1f})")
        for m, v in pos:
            r = rows[m]
            mark = "*" if m in kept else (" " if m not in chosen else "?")
            print(f"  {mark} {m.replace('neorv32_', ''):22s} {v:6.1f}  (runs positive {r[runs_key]}/3; P {r['precision']} R {r['recall']}; "
                  f"FP {r['false positives']}, missed {r['missed']}, findable/run {r['findable per run']})")
    resp = sorted({m for k in out["responsible"].values() for m in k["kept (positive in 2+ runs)"]})
    out["responsible modules (union)"] = resp
    rest = [m for m in held if m.replace("neorv32_", "") not in resp]
    x = C8.runs(V, rest, ref)
    T, L, Fh = sum(y["correct"] for y in x.values()), sum(y["listed"] for y in x.values()), 3 * sum(len(ref[m]) for m in rest)
    y = C8.runs(V, ["neorv32_" + m for m in resp], ref)
    T2, L2, F2 = sum(z["correct"] for z in y.values()), sum(z["listed"] for z in y.values()), 3 * sum(len(ref["neorv32_" + m]) for m in resp)
    out["held-out without them"] = {"modules": len(rest), "precision": f"{T}/{L} = {T / L:.3f}", "recall": f"{T}/{Fh} = {T / Fh:.3f}"}
    out["responsible modules together"] = {"modules": len(resp), "precision": f"{T2}/{L2} = {T2 / L2:.3f}", "recall": f"{T2}/{F2} = {T2 / F2:.3f}"}
    print(f"\nresponsible (union, positive in 2+ runs): {len(resp)} modules: {resp}")
    print(f"  CPU sub-units among them: {[m for m in resp if m.startswith('cpu_')]}; others: {[m for m in resp if not m.startswith('cpu_')]}")
    print(f"  together: {out['responsible modules together']}")
    print(f"held-out without them: {out['held-out without them']}  (tuning: P {Pt:.3f}, R {Rt:.3f})")
    (HERE / "locate_degradation.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
