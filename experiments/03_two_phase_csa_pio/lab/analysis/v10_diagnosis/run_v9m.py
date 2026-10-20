"""two_phase_v9m on all 41 modules, r0-r2 (user 2026-10-18: "run all 41 modules r0-r2 (about USD 6), measure against v9j, verify
independently"; generated from run_v9m.py, same readings K1-K6 and gate). Readings, fixed before any call (exact scorer; pooled over the runs):
  K1 per group (tuning 15, held-out 26, tuning_v2, heldout_v2): correct, listed, recall, precision per run and pooled, against
     v9j (r0-r2) and the simulated ceiling sim_walk_rule.json V3. GATE (FP_V9J_ANALYSIS.md section 2): tuning_v2 pooled precision
     at least v9j's + 0.05 and pooled recall at least v9j's - 0.02. Also the does-not-hurt cut against v9g on tuning_v2.
  K2 rule followed: walk-found internal primaries per run (fp_v9j_detail's strict anchoring, on v9k's own Phase 1 output;
     internal = signal, record signal, signal field), split correct / false, against v9j's per run; and how many of them a keep
     rule's list spares (the simulation keeps those).
  K3 the six entries the simulation lost (wdt reset_cause, wdt reset_wdt, gptmr irq_pnd, cpu_lsu mar, cpu_lsu amo_cmd, gpio
     port_in): found per run, against v9j.
  K4 the keep rules' targets (v9g_targets.json, K11-K13 intended cases) found per run, against v9j.
  K5 Phase 2 replies with a format problem per run, against v9j.
  K6 v9j's 85 stable false positives still listed per run.
Self-test: v9j as the candidate reproduces read_v9j.json's pooled figures per group and does not pass the gate.
  python -B run_v9m.py selftest | preview | measure;  <conda python> run_v9m.py run --remaining=<USD> --send | rerun-missing
"""
import json
import os
import sys
from collections import Counter

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402

import run_v9g as RG  # noqa: E402
import run_v9i as RI  # noqa: E402
import run_v9j as RJ  # noqa: E402
import fp_v9j_detail as FD  # noqa: E402

V, CH, HR, run_a = RG.V, RG.CH, RG.HR, RG.run_a
V9M, V9J, V9G = "two_phase_v9m", "two_phase_v9j", "two_phase_v9g"
REPS, MARGIN = (0, 1, 2), 0.32
INTERNAL = ("signal", "signal field", "record signal")
SIX = ["neorv32_wdt:reset_cause", "neorv32_wdt:reset_wdt", "neorv32_gptmr:irq_pnd", "neorv32_cpu_lsu:mar", "neorv32_cpu_lsu:amo_cmd", "neorv32_gpio:port_in"]


def load(v, m, r, part):
    f = CH.run_dir(v, MODEL, r, EFFORT) / part / f"{m}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def walk_found(v, r, mods, ref, spared):
    """per run: walk-found internal primaries (correct, false, spared) under strict anchoring on v's own Phase 1 output."""
    c = f = sp = 0
    for m in mods:
        a, p1 = load(v, m, r, "assets"), load(v, m, r, "phase1")
        if a is None or p1 is None:
            continue
        al = FD.assign_lines(m)
        kd, _ = FD.TR.kinds(m)
        concepts = {x["id"]: x for x in (p1["reply"].get("conceptual assets") or []) if isinstance(x, dict) and x.get("id")}
        left = Counter(x["Asset RTL"] for x in a["Assets"])
        ok = Counter()
        for n in ref[m]:
            if left[n] > 0:
                left[n] -= 1
                ok[n] += 1
        seen = Counter()
        for row in a["Assets"]:
            e = row["Asset RTL"]
            seen[e] += 1
            if kd.get(e, "?") not in INTERNAL:
                continue
            strict = any(e in set(concepts.get(cid, {}).get("enters through") or []) | set(concepts.get(cid, {}).get("leaves through") or [])
                         or (al.get(e, set()) & set(concepts.get(cid, {}).get("held lines") or [])) for cid in (row.get("Concepts") or []))
            if strict:
                continue
            if seen[e] <= ok[e]:
                c += 1
            else:
                f += 1
            if f"{m}:{e}" in spared:
                sp += 1
    return {"correct": c, "false": f, "spared by a keep list": sp}


def readers(v=V9M, reps=REPS):
    g, ref = V.R10.CV.groups_and_ref()
    mods = list(g["tuning"]) + list(g["held-out"])
    groups = RI.groups()
    sim = json.loads((HERE / "sim_walk_rule.json").read_text(encoding="utf-8"))
    out = {"K1": {}}
    for name, ms in groups.items():
        rows = {"candidate": RG.recall_rows(v, reps, ms), "v9j": RG.recall_rows(V9J, REPS, ms), "v9g": RG.recall_rows(V9G, REPS, ms)}
        out["K1"][name] = {k: {"runs": r, "pooled": RJ.pooled(r) if r else None} for k, r in rows.items()}
        out["K1"][name]["sim V3"] = {k: sim["V3"][name][k] for k in ("correct", "listed", "recall", "precision")}
    c, j, gg = {k: x["candidate"]["pooled"] for k, x in out["K1"].items()}, {k: x["v9j"]["pooled"] for k, x in out["K1"].items()}, {k: x["v9g"]["pooled"] for k, x in out["K1"].items()}
    t = "tuning_v2"
    out["K1 GATE (tuning_v2: precision >= v9j + 0.05 and recall >= v9j - 0.02)"] = bool(c[t] and c[t]["precision"] >= j[t]["precision"] + 0.05 and c[t]["recall"] >= j[t]["recall"] - 0.02)
    out["K1 does-not-hurt vs v9g (tuning_v2)"] = bool(c[t] and c[t]["recall"] >= gg[t]["recall"] - 0.02 and c[t]["precision"] >= gg[t]["precision"] - 0.02)
    out["K1 vs v9j per group (dR, dP)"] = {k: (round(c[k]["recall"] - j[k]["recall"], 3), round(c[k]["precision"] - j[k]["precision"], 3)) if c[k] else None for k in c}
    spared = __import__("sim_walk_rule").spared_set()
    out["K2 walk-found internal primaries per run"] = {"candidate": [walk_found(v, r, mods, ref, spared) for r in reps], "v9j": [walk_found(V9J, r, mods, ref, spared) for r in REPS]}
    def found(vv, r, cases):
        n = 0
        for case in cases:
            m, e = case.split(":", 1)
            if V.assets(vv, m, r) is not None and e in V.assets(vv, m, r):
                n += 1
        return n
    out["K3 the six simulated losses found per run"] = {"candidate": [found(v, r, SIX) for r in reps], "v9j": [found(V9J, r, SIX) for r in REPS], "of": len(SIX)}
    targets = [("neorv32_" + e if not e.startswith("neorv32_") else e) for _, e in json.loads((HERE / "v9g_targets.json").read_text(encoding="utf-8"))]
    shapes = json.loads((HERE / "new_rules" / "meta_v9h_shapes.json").read_text(encoding="utf-8"))
    for rid in ("K11", "K12", "K13"):
        targets += shapes.get(rid, {}).get("intended_cases", [])
    targets = sorted(set(targets))
    out["K4 keep targets found per run"] = {"candidate": [found(v, r, targets) for r in reps], "v9j": [found(V9J, r, targets) for r in REPS], "of": len(targets)}
    def slips(vv, r):
        n = 0
        for mm in mods:
            d = load(vv, mm, r, "phase2")
            if d is not None:
                n += any(str(p).startswith("format:") for p in d.get("problems") or [])
        return n
    out["K5 format slips (41 modules)"] = {"candidate": [slips(v, r) for r in reps], "v9j": [slips(V9J, r) for r in REPS]}
    stable = json.loads((HERE / "fp_v9j.json").read_text(encoding="utf-8"))["consistent"]
    out["K6 v9j's 85 stable FPs still listed per run"] = {"candidate": [found(v, r, ["neorv32_" + s for s in stable]) for r in reps], "v9j": [found(V9J, r, ["neorv32_" + s for s in stable]) for r in REPS], "of": len(stable)}
    return out


def measure():
    out = readers()
    (HERE / "read_v9m.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def selftest(log=print):
    c = {"prompt folder exists and passes check_lab_prompt": (LAB / "prompts" / V9M / "phase2.md").exists() and V.CK.check(V9M, log=lambda *a: None)}
    rj = json.loads((HERE / "read_v9j.json").read_text(encoding="utf-8"))["J1"]
    z = readers(V9J, REPS)
    c["zero point: v9j as the candidate reproduces read_v9j.json pooled figures and does not pass the gate"] = all(
        z["K1"][k]["candidate"]["pooled"]["correct"] == rj[k]["candidate"]["pooled"]["correct"] and z["K1"][k]["candidate"]["pooled"]["listed"] == rj[k]["candidate"]["pooled"]["listed"] for k in z["K1"]) and not z["K1 GATE (tuning_v2: precision >= v9j + 0.05 and recall >= v9j - 0.02)"]
    wf = z["K2 walk-found internal primaries per run"]["v9j"]
    c["zero point: v9j's walk-found false internals sum to 156 (160 minus the 4 record-port ones)"] = sum(x["false"] for x in wf) == 156
    bad = [k for k, v_ in c.items() if not v_]
    log(f"run_v9m self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def estimate():
    g, _ = V.R10.CV.groups_and_ref()
    ms = list(g["tuning"]) + list(g["held-out"])
    s = sum(run_a.usd(json.loads((CH.run_dir(V9J, MODEL, 0, EFFORT) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))["usage"]) for m in ms for ph in (1, 2))
    gr = sum(len(V.CK.system(V9M, ph)) / len(V.CK.system(V9J, ph)) for ph in (1, 2)) / 2
    return s, s * gr * 3


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    base, est = estimate()
    print(f"all 41 x 3 runs: 246 calls; v9j's stored r0 cost USD {base:.2f} x growth x 3 = USD {est:.2f}; needs {est + MARGIN:.2f} left; counter USD {run_a.spent(log=lambda *a: None):.2f}")


def run():
    rem = [a for a in sys.argv if a.startswith("--remaining=")]
    if not rem or not selftest(log=lambda *a: None):
        sys.exit("refused")
    _, est = estimate()
    print(f"estimate USD {est:.2f}", flush=True)
    if "--send" not in sys.argv or float(rem[0].split("=", 1)[1]) < est + MARGIN:
        sys.exit("not sent")
    g, _ = V.R10.CV.groups_and_ref()
    ms = list(g["tuning"]) + list(g["held-out"])
    V.track([CH.run_dir(V9M, MODEL, 0, EFFORT).parent])
    start = run_a.spent(log=lambda *a: None)
    for r in REPS:
        res = CH.run_many([(V9M, r)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RUN_WORKERS", "4")))
        bad = [(x["module"], x["status"]) for x in res[(V9M, r)] if x.get("status") != "done"]
        print(f"r{r} done; not done: {bad or 'none'}; so far USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)
    print(f"spent USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


def rerun_missing():
    g, _ = V.R10.CV.groups_and_ref()
    ms_all = list(g["tuning"]) + list(g["held-out"])
    start = run_a.spent(log=lambda *a: None)
    for r in REPS:
        ms = [m for m in ms_all if V.assets(V9M, m, r) is None]
        if ms:
            print(f"r{r} re-sending {[m[8:] for m in ms]}", flush=True)
            res = CH.run_many([(V9M, r)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RERUN_WORKERS", "3")))
            print(f"r{r} not done:", [(x["module"], x["status"]) for x in res[(V9M, r)] if x.get("status") != "done"] or "none", flush=True)
    print(f"spent this re-send USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "measure":
        if not selftest(log=print):
            sys.exit("self-test FAIL")
        print(json.dumps(measure(), indent=1, ensure_ascii=False)[:9000])
    elif cmd == "run":
        run()
    elif cmd == "rerun-missing":
        rerun_missing()
    else:
        {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview}[cmd]()
