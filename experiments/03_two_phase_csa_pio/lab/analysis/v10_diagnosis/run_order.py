"""Stage C, second cell: the order test (PLAN_ISOLATE_CLUSTER_ORDER.md section 8). Order A = two_phase_v9i (every keep block
right after the bar it overrides; the five false-positive bars at the end of step 4). Order B = two_phase_v9i_orderB (the
same text with every keep block moved to the end of its step: Phase 1 after the last rule, Phase 2 at the end of step 4,
so after the bars). Cell: the seven K1 modules of run_v9h.MODS, r0-r2, both orders (A's r0 comes from the all-41 run).
Readings (set 2026-10-18 before any call; exact scorer):
  O1 per keep block (the targets of v9g_targets.json for N21-N25 plus run_v9h's K11-K13 targets, inside the seven modules):
     found per run under A and under B; a block is "followed" when every target is found in 2 of 3 runs.
  O2 exact correct, listed, recall and precision on the seven modules, per run and pooled, A against B; a difference counts
     when it holds in every run and moves at least 3 pooled finds; else "no difference shown".
  O3 the consistent v9h false positives inside the seven modules still listed, A against B (the bars' effect by order).
  O4 Phase 2 replies with a format problem per run, A against B.
Self-test: the readers on two_phase_v9h r0-r2 as both A and B give identical figures and "no difference shown".

  python -B run_order.py selftest | preview
  <conda python> run_order.py run --remaining=<USD> --send      (A r1-r2 and B r0-r2 on the seven modules)
  python -B run_order.py measure
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402

import run_v9h as RH  # noqa: E402

V, CH, HR, run_a, C = RH.V, RH.CH, RH.HR, RH.run_a, RH.C
A, B = os.environ.get("ORDER_A", "two_phase_v9i"), os.environ.get("ORDER_B", "two_phase_v9i_orderB")
MODS, REPS, MARGIN = RH.MODS, RH.REPS, 0.32


def block_targets():
    t = json.loads((HERE / "v9g_targets.json").read_text(encoding="utf-8"))
    out = {}
    for rid, c in t:
        if "neorv32_" + c.split(":")[0] in MODS and rid.startswith("N"):
            out.setdefault(rid, [])
            if c not in out[rid]:
                out[rid].append(c)
    for rid, m in json.loads((HERE / "new_rules" / "meta_v9h.json").read_text(encoding="utf-8")).items():
        if rid == "K14":
            continue
        out[rid] = [c.replace("neorv32_", "") for c in m["intended_cases"] if c.split(":")[0] in MODS]
    return out


def rows(v):
    return RH.rows(v, REPS)


def readers(a, b):
    out = {}
    ra, rb = rows(a), rows(b)
    pa, pb = sum(x["correct"] for x in ra), sum(x["correct"] for x in rb)
    verdict = "no difference shown"
    if ra and rb and len(ra) == len(rb):
        if all(x["correct"] > max(y["correct"] for y in rb) for x in ra) and pa - pb >= 3:
            verdict = "A above B"
        elif all(x["correct"] > max(y["correct"] for y in ra) for x in rb) and pb - pa >= 3:
            verdict = "B above A"
    out["O2 seven modules"] = {"A": ra, "B": rb, "verdict": verdict, "pooled A": pa, "pooled B": pb}
    o1 = {}
    for rid, cases in block_targets().items():
        fa = [sum(bool(RH.found(a, r, c)) for c in cases) for r in REPS]
        fb = [sum(bool(RH.found(b, r, c)) for c in cases) for r in REPS]
        pa_ = {c: [RH.found(a, r, c) for r in REPS] for c in cases}
        pb_ = {c: [RH.found(b, r, c) for r in REPS] for c in cases}
        o1[rid] = {"targets": len(cases), "A found per run": fa, "B found per run": fb,
                   "A followed": all(sum(bool(x) for x in pa_[c]) >= 2 for c in cases), "B followed": all(sum(bool(x) for x in pb_[c]) >= 2 for c in cases)}
    out["O1 per keep block"] = o1
    fp = json.loads((HERE / "fp_v9h.json").read_text(encoding="utf-8"))
    cons = [(x["module"], x["element"]) for x in fp["consistent"] if "neorv32_" + x["module"] in MODS]
    out["O3 consistent v9h FPs in the seven modules still listed per run"] = {
        tag: [sum(1 for m, e in cons if (V.assets(v, "neorv32_" + m, r) or set()) and e in V.assets(v, "neorv32_" + m, r)) for r in REPS]
        for tag, v in (("A", a), ("B", b))} | {"of": len(cons)}
    out["O4 Phase 2 replies with a format problem per run"] = {"A": RH.slips(a, REPS), "B": RH.slips(b, REPS)}
    return out


def measure():
    out = {"A": A, "B": B, "readings": readers(A, B)}
    (HERE / "read_order.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def selftest(log=print):
    c = {}
    for v in (A, B):
        c[f"{v} exists and passes check_lab_prompt"] = (LAB / "prompts" / v / "phase1.md").exists() and V.CK.check(v, log=lambda *a: None)
    z = readers(RH.V9H, RH.V9H)
    c["zero point: v9h as both orders gives identical figures and 'no difference shown'"] = z["O2 seven modules"]["verdict"] == "no difference shown" and z["O2 seven modules"]["pooled A"] == z["O2 seven modules"]["pooled B"]
    c["block targets are reference entries of the cell modules"] = all(RH.groups()[1]["neorv32_" + t.split(":")[0]].count(t.split(":", 1)[1]) for cases in block_targets().values() for t in cases)
    bad = [k for k, v_ in c.items() if not v_]
    log(f"run_order self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def jobs():
    j = []
    for v in (A, B):
        for r in REPS:
            for m in MODS:
                if V.assets(v, m, r) is None:
                    j.append((v, r, m))
    return j


def estimate():
    j = jobs()
    s = 0.0
    for v, r, m in j:
        for ph in (1, 2):
            f = CH.run_dir(RH.V9G, MODEL, r, EFFORT) / f"phase{ph}" / f"{m}.json"
            s += run_a.usd(json.loads(f.read_text(encoding="utf-8"))["usage"])
    g = sum(len(V.CK.system(A, ph)) / len(V.CK.system(RH.V9G, ph)) for ph in (1, 2)) / 2
    return len(j), s, s * g


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    n, base, est = estimate()
    print(f"order cell: {n} module-runs to send ({2 * n} calls); v9g's stored cost of the same cells USD {base:.2f}; estimate USD {est:.2f}; needs USD {est + MARGIN:.2f} left")


def run():
    rem = [a for a in sys.argv if a.startswith("--remaining=")]
    if not rem:
        sys.exit("refused: give --remaining=<USD>")
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    n, _, est = estimate()
    print(f"{n} module-runs, estimate USD {est:.2f}", flush=True)
    if "--send" not in sys.argv:
        return
    if float(rem[0].split("=", 1)[1]) < est + MARGIN:
        sys.exit("refused: not enough budget left")
    start = run_a.spent(log=lambda *a: None)
    for v in (A, B):
        V.track([CH.run_dir(v, MODEL, 0, EFFORT).parent])
        for r in REPS:
            ms = [m for m in MODS if V.assets(v, m, r) is None]
            if not ms:
                continue
            res = CH.run_many([(v, r)], ms, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai", workers=int(os.environ.get("RUN_WORKERS", "4")))
            bad = [(x["module"], x["status"]) for x in res[(v, r)] if x.get("status") != "done"]
            print(f"{v} r{r} done; not done: {bad or 'none'}; so far USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)
    print(f"spent USD {run_a.spent(log=lambda *a: None) - start:.3f}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "measure":
        if not selftest(log=print):
            sys.exit("self-test FAIL; nothing reported")
        print(json.dumps(measure(), indent=1, ensure_ascii=False)[:8000])
    elif cmd == "run":
        run()
    else:
        {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview}[cmd]()
