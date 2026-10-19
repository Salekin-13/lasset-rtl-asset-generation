"""Precision test of two_phase_v9i (v9h + false-positive bars) on all 41 modules, run 0 (user 2026-10-18: "test the result
to see if precision has improved"). NOT sent without the cost logged first.
Readings (set 2026-10-18 before any call; exact scorer; two_phase_v9h r0 and r1 are the comparison):
  P1 per group (tuning 15, held-out 26, tuning_v2, heldout_v2): correct, listed, recall, precision against v9h r0 / r1.
     Precision improved: v9i's precision above both v9h runs on tuning_v2 AND held-out 26, with recall not below the
     lower v9h run by more than 0.02 on either. Otherwise: not shown.
  P2 the 153 consistent v9h false positives (fp_v9h.json): how many v9i still lists, per group of fp_groups; the bars'
     must-spare reference entries (meta_v9i.json): how many v9i loses that v9h r0 found.
  P3 Phase 2 replies with a format problem, against v9h r0.
Self-test: the readers on v9h r0 as the candidate reproduce v9h's own counts and "not shown".

  python -B run_v9i.py selftest | preview
  <conda python> run_v9i.py run --remaining=<USD> [--send]
  python -B run_v9i.py measure
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402

import run_v9g as RG  # noqa: E402

V, CH, HR, run_a = RG.V, RG.CH, RG.HR, RG.run_a
V9I, V9H = os.environ.get("V9I_VERSION", "two_phase_v9i"), "two_phase_v9h"
MARGIN = 0.32


def groups():
    g, _ = RG.groups()
    sp = V.splits()
    return {"tuning 15": list(g["tuning"]), "held-out 26": list(g["held-out"]), "tuning_v2": sp["tuning_v2"], "heldout_v2": sp["heldout_v2"]}


def meta():
    p = HERE / "new_rules" / "meta_v9i.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def readers(v, reps=(0,)):
    out = {"P1": {}}
    for name, ms in groups().items():
        out["P1"][name] = {"candidate": RG.recall_rows(v, reps, ms), "v9h r0-r1": RG.recall_rows(V9H, (0, 1), ms)}
    c = {k: x["candidate"][0] for k, x in out["P1"].items() if x["candidate"]}
    b = {k: x["v9h r0-r1"] for k, x in out["P1"].items()}
    improved = all(c[k]["precision"] > max(y["precision"] for y in b[k]) and c[k]["recall"] >= min(y["recall"] for y in b[k]) - 0.02
                   for k in ("tuning_v2", "held-out 26") if k in c)
    out["P1 verdict"] = "precision improved" if improved else "not shown"
    fp = json.loads((HERE / "fp_v9h.json").read_text(encoding="utf-8"))
    still = []
    for x in fp["consistent"]:
        m = "neorv32_" + x["module"]
        a = V.assets(v, m, reps[0])
        if a is not None and x["element"] in a:
            still.append(f"{x['module']}:{x['element']}")
    out["P2 consistent v9h FPs still listed"] = {"count": len(still), "of": len(fp["consistent"]), "list": still}
    lost = []
    for rid, mt in meta().items():
        for case in mt.get("must_spare", []):
            m, e = case.split(":")[0], case.split(":", 1)[1]
            if V.assets(V9H, m, 0) and e in V.assets(V9H, m, 0) and V.assets(v, m, reps[0]) is not None and e not in V.assets(v, m, reps[0]):
                lost.append(f"{rid}: {m[8:]}:{e}")
    out["P2 must-spare reference entries lost against v9h r0"] = lost
    slips = {}
    for tag, vv, r in (("candidate", v, reps[0]), ("v9h r0", V9H, 0)):
        n = 0
        for ms in (groups()["tuning 15"], groups()["held-out 26"]):
            for m in ms:
                f = CH.run_dir(vv, MODEL, r, EFFORT) / "phase2" / f"{m}.json"
                if f.exists():
                    n += any(str(p).startswith("format:") for p in json.loads(f.read_text(encoding="utf-8")).get("problems") or [])
        slips[tag] = n
    out["P3 Phase 2 replies with a format problem (41 modules)"] = slips
    return out


def measure(v=V9I):
    out = readers(v)
    (HERE / "read_v9i.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def selftest(log=print):
    c = {}
    c["prompt folder exists and passes check_lab_prompt"] = (LAB / "prompts" / V9I / "phase1.md").exists() and V.CK.check(V9I, log=lambda *a: None)
    z = readers(V9H)
    c["zero point: v9h r0 as the candidate gives its own counts and 'not shown'"] = all(
        x["candidate"][0]["correct"] == x["v9h r0-r1"][0]["correct"] for x in z["P1"].values()) and z["P1 verdict"] == "not shown"
    c["fp_v9h.json present with 153 consistent FPs"] = json.loads((HERE / "fp_v9h.json").read_text(encoding="utf-8"))["totals"]["consistent FPs"] == 153
    bad = [k for k, v_ in c.items() if not v_]
    log(f"run_v9i self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def growth():
    s = [len(V.CK.system(V9I, ph)) / len(V.CK.system(V9H, ph)) for ph in (1, 2)]
    return sum(s) / len(s)


def estimate():
    ms = groups()["tuning 15"] + groups()["held-out 26"]
    s = sum(run_a.usd(json.loads((CH.run_dir(V9H, MODEL, 0, EFFORT) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))["usage"]) for m in ms for ph in (1, 2))
    return s, s * growth()


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    base, est = estimate()
    print(f"prompt growth v9i / v9h (system text): x{growth():.3f}")
    print(f"all 41 modules, r0: 82 calls; v9h's stored r0 cost USD {base:.2f}; estimate USD {est:.2f}; needs USD {est + MARGIN:.2f} left")
    print(f"spent so far (counter) USD {run_a.spent(log=lambda *a: None):.2f}")


def run():
    rem = [a for a in sys.argv if a.startswith("--remaining=")]
    if not rem:
        sys.exit("refused: give --remaining=<USD>")
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    _, est = estimate()
    print(f"estimate USD {est:.2f}", flush=True)
    if "--send" not in sys.argv:
        return
    if float(rem[0].split("=", 1)[1]) < est + MARGIN:
        sys.exit("refused: not enough budget left")
    ms = groups()["tuning 15"] + groups()["held-out 26"]
    V.track([CH.run_dir(V9I, MODEL, 0, EFFORT).parent])
    start = run_a.spent(log=lambda *a: None)
    res = CH.run_many([(V9I, 0)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RUN_WORKERS", "4")))
    bad = [(x["module"], x["status"]) for x in res[(V9I, 0)] if x.get("status") != "done"]
    print(f"r0 done; not done: {bad or 'none'}; spent USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


def rerun_missing():
    ms = [m for m in groups()["tuning 15"] + groups()["held-out 26"] if V.assets(V9I, m, 0) is None]
    print("re-sending", [m[8:] for m in ms], flush=True)
    start = run_a.spent(log=lambda *a: None)
    if ms:
        res = CH.run_many([(V9I, 0)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RERUN_WORKERS", "3")))
        print("not done:", [(x["module"], x["status"]) for x in res[(V9I, 0)] if x.get("status") != "done"] or "none", flush=True)
    print(f"spent this re-send USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "measure":
        if not selftest(log=print):
            sys.exit("self-test FAIL; nothing reported")
        print(json.dumps(measure(), indent=1, ensure_ascii=False)[:8000])
    elif cmd == "run":
        run()
    elif cmd == "rerun-missing":
        rerun_missing()
    else:
        {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview}[cmd]()
