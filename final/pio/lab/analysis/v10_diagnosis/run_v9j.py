"""two_phase_v9j on all 41 modules, r0-r2 (user 2026-10-18: "run it on all 41 modules, r0-r2 (about USD 6.4), measure against
v9g and v9h"). Readings (set before any call; exact scorer):
  J1 per group (tuning 15, held-out 26, tuning_v2, heldout_v2): correct, listed, recall, precision per run and pooled, against
     v9g (held-out r0-r2, tuning r0) and v9h (r0-r1 all; the 7 cell modules r0-r2) and v9i r0. Version-table cuts: on
     tuning_v2, recall and precision each not below v9g's by more than 0.02 (does-not-hurt); "better than v9h" when pooled
     precision is above v9h's pooled on every group and pooled recall is not below v9h's pooled by more than 0.02 on any.
  J2 the 153 consistent v9h false positives still listed per run; the bars' must-spare entries lost against v9h r0.
  J3 the control unit's reference entries found per run (the bar fix's target) against v9i r0 and v9h r0-r1.
  J4 Phase 2 replies with a format problem per run against v9h r0 and v9i r0.
  python -B run_v9j.py selftest | preview | measure;  <conda python> run_v9j.py run --remaining=<USD> --send | rerun-missing
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402

import run_v9g as RG  # noqa: E402
import run_v9i as RI  # noqa: E402

V, CH, HR, run_a = RG.V, RG.CH, RG.HR, RG.run_a
V9J, V9I, V9H, V9G = "two_phase_v9j", "two_phase_v9i", "two_phase_v9h", "two_phase_v9g"
REPS, MARGIN = (0, 1, 2), 0.32


def pooled(rows):
    c, l, f = sum(x["correct"] for x in rows), sum(x["listed"] for x in rows), sum(x["findable"] for x in rows)
    return {"correct": c, "listed": l, "findable": f, "recall": round(c / f, 3) if f else None, "precision": round(c / l, 3) if l else None}


def readers(v=V9J, reps=REPS):
    out = {"J1": {}}
    for name, ms in RI.groups().items():
        rows = {"candidate": RG.recall_rows(v, reps, ms), "v9i r0": RG.recall_rows(V9I, (0,), ms), "v9h": RG.recall_rows(V9H, (0, 1), ms), "v9g": RG.recall_rows(V9G, (0, 1, 2), ms)}
        out["J1"][name] = {k: {"runs": r, "pooled": pooled(r) if r else None} for k, r in rows.items()}
    c, h, g = {k: x["candidate"]["pooled"] for k, x in out["J1"].items()}, {k: x["v9h"]["pooled"] for k, x in out["J1"].items()}, {k: x["v9g"]["pooled"] for k, x in out["J1"].items()}
    out["J1 does-not-hurt vs v9g (tuning_v2)"] = bool(c["tuning_v2"] and g["tuning_v2"] and c["tuning_v2"]["recall"] >= g["tuning_v2"]["recall"] - 0.02 and c["tuning_v2"]["precision"] >= g["tuning_v2"]["precision"] - 0.02)
    out["J1 better than v9h"] = all(c[k] and h[k] and c[k]["precision"] > h[k]["precision"] and c[k]["recall"] >= h[k]["recall"] - 0.02 for k in c)
    fp = json.loads((HERE / "fp_v9h.json").read_text(encoding="utf-8"))
    out["J2 consistent v9h FPs still listed per run"] = [sum(1 for x in fp["consistent"] if (V.assets(v, "neorv32_" + x["module"], r) or set()) and x["element"] in V.assets(v, "neorv32_" + x["module"], r)) for r in reps] + [f"of {len(fp['consistent'])}"]
    lost = {}
    for rid, mt in RI.meta().items():
        for case in mt.get("must_spare", []):
            m, e = case.split(":")[0], case.split(":", 1)[1]
            if V.assets(V9H, m, 0) and e in V.assets(V9H, m, 0):
                miss = [r for r in reps if V.assets(v, m, r) is not None and e not in V.assets(v, m, r)]
                if len(miss) >= 2:
                    lost.setdefault(rid, []).append(f"{m[8:]}:{e} missed in {miss}")
    out["J2 must-spare entries v9h r0 found, v9j misses in 2+ runs"] = lost
    m = "neorv32_cpu_control"
    ref = RG.groups()[1][m]
    out["J3 control unit correct per run"] = {"v9j": [sum(HR.found_occ(ref, HR.names(v, r, m)).values()) for r in reps if HR.names(v, r, m) is not None],
                                              "v9i r0": [sum(HR.found_occ(ref, HR.names(V9I, 0, m)).values())], "v9h r0-r1": [sum(HR.found_occ(ref, HR.names(V9H, r, m)).values()) for r in (0, 1)], "findable": len(ref)}
    def slips(vv, r):
        n = 0
        for ms in (RI.groups()["tuning 15"], RI.groups()["held-out 26"]):
            for mm in ms:
                f = CH.run_dir(vv, MODEL, r, EFFORT) / "phase2" / f"{mm}.json"
                if f.exists():
                    n += any(str(p).startswith("format:") for p in json.loads(f.read_text(encoding="utf-8")).get("problems") or [])
        return n
    out["J4 format slips (41 modules)"] = {"v9j": [slips(v, r) for r in reps], "v9i r0": slips(V9I, 0), "v9h r0": slips(V9H, 0)}
    return out


def measure():
    out = readers()
    (HERE / "read_v9j.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def selftest(log=print):
    c = {"prompt folder exists and passes check_lab_prompt": (LAB / "prompts" / V9J / "phase1.md").exists() and V.CK.check(V9J, log=lambda *a: None)}
    z = readers(V9H, (0, 1))
    c["zero point: v9h as the candidate reproduces its own pooled figures and is not 'better than v9h'"] = all(x["candidate"]["pooled"] == x["v9h"]["pooled"] for x in z["J1"].values()) and not z["J1 better than v9h"]
    bad = [k for k, v_ in c.items() if not v_]
    log(f"run_v9j self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def estimate():
    ms = RI.groups()["tuning 15"] + RI.groups()["held-out 26"]
    s = sum(run_a.usd(json.loads((CH.run_dir(V9I, MODEL, 0, EFFORT) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))["usage"]) for m in ms for ph in (1, 2))
    g = sum(len(V.CK.system(V9J, ph)) / len(V.CK.system(V9I, ph)) for ph in (1, 2)) / 2
    return s, s * g * 3


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    base, est = estimate()
    print(f"all 41 x 3 runs: 246 calls; v9i's stored r0 cost USD {base:.2f} x growth x 3 = USD {est:.2f}; needs {est + MARGIN:.2f} left; counter USD {run_a.spent(log=lambda *a: None):.2f}")


def run():
    rem = [a for a in sys.argv if a.startswith("--remaining=")]
    if not rem or not selftest(log=lambda *a: None):
        sys.exit("refused")
    _, est = estimate()
    print(f"estimate USD {est:.2f}", flush=True)
    if "--send" not in sys.argv or float(rem[0].split("=", 1)[1]) < est + MARGIN:
        sys.exit("not sent")
    ms = RI.groups()["tuning 15"] + RI.groups()["held-out 26"]
    V.track([CH.run_dir(V9J, MODEL, 0, EFFORT).parent])
    start = run_a.spent(log=lambda *a: None)
    for r in REPS:
        res = CH.run_many([(V9J, r)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RUN_WORKERS", "4")))
        bad = [(x["module"], x["status"]) for x in res[(V9J, r)] if x.get("status") != "done"]
        print(f"r{r} done; not done: {bad or 'none'}; so far USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)
    print(f"spent USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


def rerun_missing():
    ms_all = RI.groups()["tuning 15"] + RI.groups()["held-out 26"]
    start = run_a.spent(log=lambda *a: None)
    for r in REPS:
        ms = [m for m in ms_all if V.assets(V9J, m, r) is None]
        if ms:
            print(f"r{r} re-sending {[m[8:] for m in ms]}", flush=True)
            res = CH.run_many([(V9J, r)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RERUN_WORKERS", "3")))
            print(f"r{r} not done:", [(x["module"], x["status"]) for x in res[(V9J, r)] if x.get("status") != "done"] or "none", flush=True)
    print(f"spent this re-send USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "measure":
        if not selftest(log=print):
            sys.exit("self-test FAIL")
        print(json.dumps(measure(), indent=1, ensure_ascii=False)[:7000])
    elif cmd == "run":
        run()
    elif cmd == "rerun-missing":
        rerun_missing()
    else:
        {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview}[cmd]()
