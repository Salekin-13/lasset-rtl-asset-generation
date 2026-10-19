"""Every number REPORT.md states, from the stored results of this study (read-only; writes report_numbers.json).

Adds two code readings used for the causes table:
  B (assessment vs reporting), for the primary-making rules v10 breaks (rule_breaks M2 kind "keep"): of the (element, run)
    pairs where an element the rule keeps alone is not primary in v10, how many are absent from every Phase 2 row (never
    assessed), labelled secondary, or not reported.
  D (different thresholds on similar cases), for each staged-test target: in each (module, run) of full v10, are the
    target's consistently barred elements split (some primary, some not)? Share of (module, run) with a split.

  python -B report_numbers.py
"""
import json
import os
import sys
from collections import Counter

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, register  # noqa: E402

ISO = register()
import ladder as L  # noqa: E402
import rule_breaks as RB  # noqa: E402

CH = RB.CH


def load(name):
    p = HERE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = {"read_v10": load("read_v10.json"), "blindspots": {k: v for k, v in (load("blindspots.json") or {}).items() if not k.endswith("list")},
           "ladder_round2": load("ladder_round2.json"), "ladder_round1": load("ladder_round1.json"),
           "core_clash": load("core_clash.json"), "p1probe": load("p1probe_P1-23.json"),
           "read_v11n": {k: v for k, v in (load("read_v11n.json") or {}).items() if " " not in k},
           "read_v11n2": {k: v for k, v in (load("read_v11n2.json") or {}).items() if " " not in k},
           "read_v11n3": {k: v for k, v in (load("read_v11n3.json") or {}).items() if " " not in k}}
    rb = load("rule_breaks.json")
    out["M2 top"] = sorted(((k, {x: v[x] for x in ("title", "kind", "consistent-bar elements", "v10 broken pairs",
                                                    "v10 broken pairs on reference elements", "v10 modules with a break",
                                                    "v10 break rate", "v9 broken pairs")}) for k, v in rb["M2"].items()),
                           key=lambda kv: -kv[1]["v10 broken pairs"])[:20]
    out["M5"] = rb["M5"]
    out["targets"] = rb["targets"]
    groups, refl = RB.CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    lst, _ = RB.primaries(RB.V10, mods)
    # B: keep rules broken in v10
    R, want, _ = RB.load_latest(mods)
    import analyze_isolation as AN
    b = {}
    for k, v in rb["M2"].items():
        if not v.get("kind", "").startswith("keep") or not v["v10 broken pairs"]:
            continue
        rid, ph = k.split()
        c = Counter()
        for m in mods:
            if (rid, ph, m, 0) not in R or (rid, ph, m, 1) not in R:
                continue
            s0, s1 = AN.names(R[(rid, ph, m, 0)], "spared"), AN.names(R[(rid, ph, m, 1)], "spared")
            for e in {e for e in s0 if e in s1}:
                for r in RB.REPS:
                    if e in lst[(r, m)]:
                        continue
                    rec = json.loads((CH.run_dir(RB.V10, "gpt-5.6-luna", r, "high") / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
                    a = json.loads((CH.run_dir(RB.V10, "gpt-5.6-luna", r, "high") / "assets" / f"{m}.json").read_text(encoding="utf-8"))
                    st, _ = L.states(rec, m, e, a)
                    c[st] += 1
        b[k] = dict(c)
    out["B keep rules: state of the elements they keep alone, where v10 does not list them primary"] = b
    # D: within-run splits of each target's consistently barred elements
    d = {}
    for t, x in (load("plan_round1.json") or {}).items():
        B_ = L.bars(t, x["modules"])
        split = total = 0
        for m in x["modules"]:
            if len(B_[m]) < 2:
                continue
            for r in RB.REPS:
                s = {e in lst[(r, m)] for e in B_[m]}
                total += 1
                split += len(s) == 2
        d[t] = [split, total]
    out["D split (module, run) / (module, run) with 2+ barred elements"] = d
    calib = load("calib.json")
    if calib:
        out["calibration"] = {k: v for k, v in calib.items() if k != "_c2 sets"}
    (HERE / "report_numbers.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({"B": b, "D": d}, indent=1))


if __name__ == "__main__":
    main()
