"""Small check of round 1 (v12t, tighten_P1-23.json) on cpu_icc and cpu_control r2-r5 (user 2026-10-17: "Run round 1 (v12t)
rule-alone on cpu_icc and cpu_control r2-r5 (8 requests, about USD 0.14), with readings set before sending: icc_rx_i.ack
barred in at least 3 of 4, frontend_i.instr barred in at most 1 of 4. Then report and carry round 1 if it holds.").

Readings (the user's, set before sending; "barred" = the reply's barred list covers it, the element or a record it is a
field of):
  C1 cpu_icc icc_rx_i.ack barred in at least 3 of 4 (r2-r5) -> holds; else not.
  C2 cpu_control frontend_i.instr barred in at most 1 of 4 (r2-r5) -> holds; else not.
  Round 1 is carried if both hold. Stored r0-r1 (icc 2/2, frontend_i.instr 0/2) are reported with them.

  python -B p1t1check.py selftest
  <conda python> p1t1check.py run      (cap 8)
  python -B p1t1check.py measure       (writes p1t1check.json)
"""
import json
import sys

import p1tighten as PT  # registers v12t

ISO, CH, L, P, run_a = PT.ISO, PT.CH, PT.L, PT.P, PT.run_a
HERE, MODEL, EFFORT, TIGHT = PT.HERE, PT.MODEL, PT.EFFORT, PT.TIGHT
ICC, CTL = "neorv32_cpu_icc", "neorv32_cpu_control"
REPS = (2, 3, 4, 5)


def jobs():
    ISO.use("v12t")
    jl, tx = ISO.jobs([ICC, CTL], reps=REPS, rules=["P1-23"], phases=("P1",))
    return jl, tx, [j for j in jl if not ISO.path(*j).exists()]


def selftest(log=print):
    checks = {}
    ISO.use("v12t")
    tt = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    checks["v12t text = tighten_P1-23.json"] = tt["P1-23"]["P1"] == P.LF.join(TIGHT)
    for m in (ICC, CTL):
        stored = [json.loads((ISO.run_root(rep=r) / "P1" / "P1-23" / f"{m}.json").read_text(encoding="utf-8")) for r in (0, 1)]
        checks[f"{m[8:]}: request = stored r0-r1 requests (user and system sha)"] = (
            {s["user sha"] for s in stored} == {CH.sha12(ISO.user(m, "P1-23", "P1", tt))}
            and {s["system sha"] for s in stored} == {CH.sha12(ISO.system("P1"))})
    ISO.use("v9")
    jl, _, todo = jobs()
    ISO.use("v9")
    checks["8 requests, none stored yet"] = len(jl) == 8 and len(todo) == 8
    bad = [k for k, v in checks.items() if not v]
    log(f"p1t1check self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def run():
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    jl, tx, todo = jobs()
    if len(todo) > 8:
        sys.exit("more than 8 requests; nothing sent")
    print(f"v12t: sending {len(todo)}; spent so far USD {run_a.spent(log=lambda *a: None):.2f}")
    ISO.run(todo, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=8)


def measure():
    d = PT.load("v12t", [ICC, CTL], range(6))
    icc = [bool(PT.covered(x, ["icc_rx_i.ack"])) for x in d[ICC]]
    ins = [bool(PT.covered(x, ["frontend_i.instr"])) for x in d[CTL]]
    c1, c2 = sum(icc[2:]), sum(ins[2:])
    out = {"C1 icc_rx_i.ack barred r2-r5": f"{c1}/4", "C1": "holds" if c1 >= 3 else "not",
           "C2 frontend_i.instr barred r2-r5": f"{c2}/4", "C2": "holds" if c2 <= 1 else "not",
           "per repeat r0-r5 icc_rx_i.ack": icc, "per repeat r0-r5 frontend_i.instr": ins,
           "applies r0-r5": {m[8:]: [x.get("applies") if isinstance(x, dict) else None for x in d[m]] for m in (ICC, CTL)}}
    out["carry round 1"] = out["C1"] == "holds" and out["C2"] == "holds"
    (HERE / "p1t1check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "run": run, "measure": measure}[sys.argv[1]]()
