"""Diagnosis round 2 (user 2026-10-16): "if a scope problem causes the issue, find suitable way to address it" (cpu_alu);
"find the cause of the conflict when clustered with other rules" (cpu_regfile); "do the test for diagnosis".
Diagnostic cells only; the final Phase 1 prompt runs whole.

Wordings (exact line replacements in v10 phase1.md; F1 and A1 as in p1fixpair.py):
  WVX  Working values, line 77: drop ", although step 2 would call them a decision".
  A2   A1 plus, Access command fields line 158 (Scope): "... or memory words, or those of an instance it passes the
       access on to (not a cache's copies)."; line 160 (Exceptions): "a select routing it on (that select only, not the
       fields it is decoded from),". Basis: the rule's own Outcome ("part of the information the access writes or
       reads, not information of their own") holds for a register an instance holds; only the select is routing; step 6
       ("Skip ports that only decide the information"). In cpu_alu the CSRs sit in the FPU / CFU instances and A1
       worked in imem (own memory) but not in cpu_alu (routed to instances).
Cells (luna, high, v10's Phase 1 format):
  T1 P1diag__K3_K6_noWV  K3 (A1) + K6 (F1, WVX)   cpu_regfile r0-r3
  T2 P1fix__K3_K6         K3 (A1) + K6 (F1)        cpu_regfile r4-r7 (same prompt as its stored r0-r3)
  S1 P1diag__K3A2_K6      K3 (A2) + K6 (F1)        cpu_alu r0-r3          <- P1fix__K3_K6 cpu_alu r0-r3 (A1)
  S2 P1diag__K3A2         K3 (A2)                  5 modules r0-r1        <- P1fix__K3 (A1), P1cluster__K3 (v10)
Measures: Access command fields' consistent rule-alone Phase 1 bars named (p1probe.p1_named); a cpu_regfile reply is
  broken when it names at least half of its 6 barred signals (they break all or none); recall guard as in p1fixpair.
Readings (set 2026-10-16 before sending):
  W1 residual: P1fix__K3_K6 cpu_regfile over r0-r7 (8 replies): at most 2/8 broken -> the residual is chance (K3 alone
     breaks 1 of 4); 4/8 or more -> a real residual; 3/8 -> no answer.
  W2 Working values: T1 at most 1/4 broken and W1 real -> its clause is a second cause; T1 2/4 or more -> not its
     clause; otherwise no answer.
  S1 scope fix: cpu_alu r0-r3 (20 pairs): at most 2/20 named -> fixed; 6/20 or more -> not fixed; 3-5 -> no answer
     (the R2 cuts of p1fixpair; A1 gave 10/20).
  S2 harm: per module, named not above P1fix__K3 (A1) by more than 2 (chosen), recall guard not below it by more than
     0.05 (chosen).

  python -B p1diag2.py selftest
  <conda python> p1diag2.py run       (at most 22 new calls)
  python -B p1diag2.py measure        (writes p1diag2.json)
"""
import json
import os
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import p1clusters as PC  # noqa: E402
import p1pairs as PP  # noqa: E402
import p1fixpair as FX  # noqa: E402
import rule_breaks as RB  # noqa: E402
import run_a  # noqa: E402

WVX = {77: (", although step 2 would call them a decision", "")}
A2 = {**FX.A1,
      158: ("or memory words (not a cache's copies).",
            "or memory words, or those of an instance it passes the access on to (not a cache's copies)."),
      160: ("a select routing it on,", "a select routing it on (that select only, not the fields it is decoded from),")}
REG, ALU = "neorv32_cpu_regfile", "neorv32_cpu_alu"


def specs():
    K = PP.clusters()
    return {
        "P1diag__K3_K6_noWV": (K["K3"] + K["K6"], {**FX.F1, **FX.A1, **WVX}, [REG], (0, 1, 2, 3)),
        "P1fix__K3_K6": (K["K3"] + K["K6"], {**FX.F1, **FX.A1}, [REG], (4, 5, 6, 7)),
        "P1diag__K3A2_K6": (K["K3"] + K["K6"], {**FX.F1, **A2}, [ALU], (0, 1, 2, 3)),
        "P1diag__K3A2": (K["K3"], A2, FX.FIVE, (0, 1)),
    }


def text_of(name):
    keep, fixes, _, _ = specs()[name]
    return FX.apply(P.build_keep(keep), fixes)


def selftest(log=print):
    import check_new_rules as CN
    checks = {}
    for name, (keep, fixes, mods, reps) in specs().items():
        base = P.build_keep(keep).split(P.LF)
        t = text_of(name).split(P.LF)
        diff = [i for i, (a, b) in enumerate(zip(base, t)) if a != b]
        want = {FX.fixed_line(n, fixes) for n in fixes}
        checks[f"{name}: only the fixed lines differ"] = len(t) == len(base) and len(diff) == len(fixes) and all(t[i] in want for i in diff)
        active = {P.base_title(x) for _, _, x in P.blocks(t, t.index("OUTPUT"))}
        checks[f"{name}: active rules as planned"] = active == set(keep)
        log(f"{name}: {len(P.LF.join(t).split())} words; fixed lines {sorted(fixes)}; modules {[m[8:] for m in mods]}; repeats {reps}")
    # T2 reuses the stored cell: same prompt on disk, stored r0-r3 carry today's sha
    disk = (P.LAB / "prompts" / "diag_v10" / "P1fix__K3_K6" / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF)
    sha = CH.sha12(CK.system("diag_v10/P1fix__K3_K6", 1))
    stored = {json.loads((L.cell_dir("P1fix__K3_K6", r) / "phase1" / f"{REG}.json").read_text(encoding="utf-8"))["system sha"] for r in range(4)}
    checks["P1fix__K3_K6: prompt on disk = builder, stored r0-r3 sha = today's"] = disk == text_of("P1fix__K3_K6") and stored == {sha}
    for title, fixes in (("Working values", WVX), ("Access command fields", A2)):
        blk = [FX.fixed_line(n, fixes) if n in fixes else FX.V10P1[n - 1] for a, b, t in P.blocks(FX.V10P1, FX.V10P1.index("OUTPUT"))
               if P.base_title(t) == title for n in range(a + 1, b + 1)]
        checks[f"{title} fixed text passes check_new_rules ({len(P.LF.join(blk).split())} words)"] = not CN.check_text("X", "P1", P.LF.join(blk))
    for m in FX.FIVE:
        checks[f"OLD P1fix__K3 has {m[8:]} r0-r1"] = all((L.cell_dir("P1fix__K3", r) / "phase1" / f"{m}.json").exists() for r in (0, 1))
    bad = [k for k, v in checks.items() if not v]
    log(f"p1diag2 self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def run():
    from concurrent.futures import ThreadPoolExecutor
    if not selftest():
        sys.exit("self-test FAIL; nothing sent")
    jobs, stop = [], CH._new_run_flag()
    for name, (keep, fixes, mods, reps) in specs().items():
        v = P.cell_version(name, text_of(name))
        L.track_folders([name])
        for rep in reps:
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            call = CH.openai(MODEL, EFFORT, out=out, poll=5)
            jobs += [(v, m, out, call) for m in mods if not (out / "phase1" / f"{m}.json").exists()]
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.02:.2f}); spent so far USD {spent:.2f}")
    if len(jobs) > 22:
        sys.exit("more than the 22 planned calls; nothing sent")

    def one(j):
        threading.current_thread().lab_stop = stop
        v, m, out, call = j
        return CH._ask(call, CK.system(v, 1), CH.user_message(v, 1, m), out / "phase1" / f"{m}.json",
                       lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": v, "phase": 1},
                       adapt=CH.from_format_phase1).get("problems")
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("done", len(res), "; problems", res, "; spent after USD", round(run_a.spent(log=lambda *a: None), 2))


def measure():
    groups, refl = RB.CV.groups_and_ref()
    dec = PC.decisions(groups["tuning"] + groups["held-out"])

    def per(cell, m, reps):
        bars = sorted(dec["P1-23"].get(m, ()))
        ks, g, n = [], 0, 0
        for r in reps:
            rec = json.loads((L.cell_dir(cell, r) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
            ks.append(sum(P.p1_named(rec, m, e) == "named" for e in bars))
            ref = sorted(refl.get(m, ()))
            g += sum(P.p1_named(rec, m, e) != "not in Phase 1" for e in ref)
            n += len(ref)
        return ks, len(bars), (g / n if n else None)
    out = {}
    pooled, nb = per("P1fix__K3_K6", REG, range(8))[:2]
    br = sum(1 for k in pooled if 2 * k >= nb)
    t1, nb1 = per("P1diag__K3_K6_noWV", REG, range(4))[:2]
    b1 = sum(1 for k in t1 if 2 * k >= nb1)
    w1 = "chance" if br <= 2 else "real residual" if br >= 4 else "no answer"
    w2 = ("Working values' clause is a second cause" if b1 <= 1 and w1 == "real residual" else
          "not Working values' clause" if b1 >= 2 else "no answer")
    out["W1"] = {"per reply r0-r7": pooled, "broken": f"{br}/8", "reading": w1}
    out["W2"] = {"per reply r0-r3": t1, "broken": f"{b1}/4", "reading": w2}
    s1, _, _ = per("P1diag__K3A2_K6", ALU, range(4))
    a1, _, _ = per("P1fix__K3_K6", ALU, range(4))
    out["S1"] = {"A2 per reply": s1, "A1 per reply": a1, "named A2": sum(s1),
                 "reading": "fixed" if sum(s1) <= 2 else "not fixed" if sum(s1) >= 6 else "no answer"}
    harm = {}
    for m in FX.FIVE:
        k2, nbm, g2 = per("P1diag__K3A2", m, (0, 1))
        k1, _, g1 = per("P1fix__K3", m, (0, 1))
        k0, _, g0 = per("P1cluster__K3", m, (0, 1))
        flag = sum(k2) > sum(k1) + 2 or (g2 is not None and g1 is not None and g2 < g1 - 0.05)
        harm[m[8:]] = {"A2": k2, "A1": k1, "v10": k0, "guard A2 / A1 / v10": [round(g2, 2), round(g1, 2), round(g0, 2)], "flag": flag}
    out["S2"] = harm
    print(json.dumps(out, indent=1))
    (HERE / "p1diag2.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "run": run, "measure": measure}[sys.argv[1]]()
