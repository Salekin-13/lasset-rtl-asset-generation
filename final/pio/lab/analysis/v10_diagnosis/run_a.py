"""Step A of PLAN.md: the luna runs (user 2026-10-16: "start the luna runs: v10 r0-r2 on all 41 modules and the 4 untested
wordings. Show me the cost estimate before sending", then "auto run the tests").

  python run_a.py preview      gates + cost estimate; sends nothing (default Python is enough)
  <conda python> run_a.py a1   v10 r0-r2, all 41 modules (chain.run_many, as notebook cell 9 runs v9)
  <conda python> run_a.py a2   rule-alone: v10e1 (P1-17, P1 + P2) and v10u (P1-HO P1, P1-26 P2), 41 modules x 2 repeats
  python run_a.py spent        USD spent so far by this study's luna run folders (stored usage)

Gates before any send: v10's system prompt sha12 equals the build's (9385aa458632 / a4719593614e); the project prompt
checker passes; the rule-alone self-test (stub executor) passes for each variant; no stored record was asked with another
message (chain's and isolation's own guards also stop on that).
A1 estimate: v9's stored usage per (module, phase, run), input scaled by the v10 / v9 system-prompt pre-token ratio of
that phase, cached share and output as v9's. A2 estimate: isolation.preview (input) plus the measured mean of the closest
earlier luna run (P1-17: v10r's own P1-17 run; the others: the v10r mean per request).
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, ROOT, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import cost_estimate as CE  # noqa: E402
import labkit as K  # noqa: E402

SHAS = {1: "9385aa458632", 2: "a4719593614e"}
ALL = K.gt_modules()["tuning"] + K.gt_modules()["heldout"]
A2 = [("v10e1", ["P1-17"]), ("v10u", ["P1-HO", "P1-26"])]
P = CE.PRICES[MODEL]


def usd(u):
    c = u.get("cached") or 0
    return ((u["in"] - c) * P["in"] + c * P["cached"] + (u.get("out") or 0) * P["out"]) / 1e6


def gates(log=print):
    ok = True
    for ph in (1, 2):
        s = CH.sha12(CK.system(V10, ph))
        log(f"v10 phase {ph} system sha12 {s} (build {SHAS[ph]}): {'ok' if s == SHAS[ph] else 'DIFFERENT'}")
        ok &= s == SHAS[ph]
    ok &= bool(CK.check(V10, log=lambda *a: None))
    log(f"prompt checker on v10: {'ok' if ok else 'FAIL'}")
    for v, _ in A2:
        ISO.use(v)
        ok &= ISO.selftest(log=log)
    ISO.use("v9")
    return ok


def estimate_a1(log=print):
    r9 = {1: CE.pretokens(CK.system("two_phase_v9", 1)), 2: CE.pretokens(CK.system("two_phase_v9", 2))}
    r10 = {1: CE.pretokens(CK.system(V10, 1)), 2: CE.pretokens(CK.system(V10, 2))}
    tot, hi, n = 0.0, 0.0, 0
    for r in (0, 1, 2):
        d = CH.run_dir("two_phase_v9", MODEL, r, EFFORT)
        for ph in (1, 2):
            for m in ALL:
                u = json.loads((d / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))["usage"]
                sys9 = r9[ph] * 1.0
                extra = (r10[ph] - r9[ph]) * (u["in"] / max(1, sys9 + CE.pretokens(CH.user_message("two_phase_v9", 1, m))))
                u2 = {"in": u["in"] + extra, "cached": (u.get("cached") or 0) * (u["in"] + extra) / u["in"], "out": u.get("out") or 0}
                tot += usd(u2)
                hi += usd({**u2, "out": u2["out"] * 1.15})
                n += 1
    log(f"A1 v10 r0-r2 x 41 modules: {n} calls; estimate USD {tot:.2f} (v9's output per call), USD {hi:.2f} if output is "
        f"15% longer; system prompt pre-tokens v9 -> v10: phase 1 {r9[1]} -> {r10[1]}, phase 2 {r9[2]} -> {r10[2]}")
    return tot, hi


def estimate_a2(log=print):
    root = LAB / "runs" / "rule_isolation_v10r" / f"{MODEL}__{EFFORT}"
    p17 = [usd(json.loads(f.read_text(encoding="utf-8"))["usage"]) for f in root.glob("r*/P*/P1-17/*.json")]
    allr = [usd(json.loads(f.read_text(encoding="utf-8"))["usage"]) for f in root.glob("r*/P*/*/*.json")]
    m17, mall = sum(p17) / len(p17), sum(allr) / len(allr)
    tot = 0.0
    for v, rules in A2:
        ISO.use(v)
        jl, tx = ISO.jobs(None, reps=(0, 1), rules=rules)
        ISO.preview(jl, tx, MODEL, EFFORT, log=log)
        left = [j for j in jl if not ISO.path(*j, MODEL, EFFORT).exists()]
        est = sum(m17 if j[0] == "P1-17" else mall for j in left)
        log(f"  {v} {rules}: {len(left)} to send; at the measured mean of the closest earlier luna run: USD {est:.2f}")
        tot += est
    ISO.use("v9")
    return tot


def send_a1():
    os.chdir(ROOT)
    for ph in (1, 2):
        assert CH.sha12(CK.system(V10, ph)) == SHAS[ph], "v10 prompt changed since the build"
    assert CK.check(V10), "prompt check failed"
    jobs = [(V10, r) for r in (0, 1, 2)]
    res = CH.run_many(jobs, ALL, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5), MODEL, EFFORT, executor="openai")
    for v, rep in jobs:
        print(f"--- {v} r{rep}:", json.dumps(CH.readings(v, MODEL, rep, ALL, EFFORT), indent=1, default=str), flush=True)
    return res


def send_a2():
    for v, rules in A2:
        ISO.use(v)
        if not ISO.selftest(log=print):
            raise SystemExit(f"{v}: self-test failed")
        jl, tx = ISO.jobs(None, reps=(0, 1), rules=rules)
        ISO.run(jl, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=24)
        ISO.measured(jl, MODEL, EFFORT)
    ISO.use("v9")


def spent(log=print):
    tot = 0.0
    folders = [CH.run_dir(V10, MODEL, r, EFFORT) for r in (0, 1, 2)] + \
              [LAB / "runs" / ISO.VARIANTS[v]["run"] / f"{MODEL}__{EFFORT}" for v, _ in A2]
    extra = HERE / "spent_extra_folders.json"          # later steps add their run folders here
    if extra.exists():
        folders += [Path(p) for p in json.loads(extra.read_text(encoding="utf-8"))]
    for d in folders:
        s, n = 0.0, 0
        for f in d.glob("**/*.json"):
            if f.parent.name.startswith("_"):
                continue
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                u = rec.get("usage")
            except Exception:
                continue
            if str(rec.get("note") or "").startswith("copied from"):
                continue                                 # 2026-10-17: a reused reply, already billed where it was asked
                                                         # (generalised for PLAN_COMPARE's copies; every copy's note starts so)
            if isinstance(u, dict) and u.get("in") is not None:
                s += usd(u)
                n += 1
        for fl in sorted(set(d.glob("**/_failed_calls.jsonl"))):   # failed calls are billed too (2026-10-17: also the
                                                                     # logs inside run subfolders, missed before)
            for line in fl.read_text(encoding="utf-8").splitlines():
                try:
                    u = json.loads(line).get("usage")
                    if isinstance(u, dict) and u.get("in") is not None:
                        s += usd(u)
                        n += 1
                except Exception:
                    pass
        log(f"  {d.relative_to(LAB)}: {n} billed replies, USD {s:.2f}")
        tot += s
    log(f"spent by this study so far: USD {tot:.2f}")
    return tot


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if cmd == "preview":
        ok = gates()
        lo, hi = estimate_a1()
        a2 = estimate_a2()
        print(f"TOTAL step A estimate: USD {lo + a2:.2f} (up to {hi + a2:.2f}); gates {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)
    elif cmd == "a1":
        send_a1()
    elif cmd == "a2":
        send_a2()
    elif cmd == "spent":
        spent()
