"""Confirmation tests of the two classifications in CONFLICT_CLASSIFICATION.md (user 2026-10-17: "Run the cpu_regfile test
(T0-T3, 8 repeats each, interleaved) and the 4-call cpu_alu test of Fix 2, with the readings from
CONFLICT_CLASSIFICATION.md set before sending, and report."). Diagnostic cells only; the final Phase 1 prompt runs whole.

Wordings (exact replacements in v10 phase1.md; FIX_PROPOSALS.md shows them side by side):
  FIX1  line 7, step 2: "... such a decision is information of its own unless a rule's bar below covers it; check the bars
        before step 3 splits it or step 5 keeps it, and where one covers it, the bar decides (Precedence)."
  SCOPE line 158 (the regfile text lens's alternative): appends "The record port need not be a bus request record port: a
        processor's control record that names which of this unit's own registers a read or write reaches, and whether a
        write happens or is forced, carries such accesses; those register numbers are register-select address bits, not
        the access address of a memory's stored words."
  FIX2  A2 (p1diag2.py: lines 158, 160, 162, 168) plus line 159 criterion (2): "(2) a write enable whose assignment reads
        only these fields and signals decoded from them (a select (b) keeps counts as one), and whose only use lets a
        register or FIFO take the written data, in this unit or at the write-enable input of an instance the access is
        passed on to (judge that input from its port name, and say so)."
  F1    line 141 (p1fixpair.py).
Cells (luna, high, v10's Phase 1 format; all 36 calls sent in one interleaved batch):
  P1t3__T0   K3 + K6, v10 text (control)                 cpu_regfile r0-r7
  P1t3__T1   K3 + K6 + FIX1                              cpu_regfile r0-r7
  P1t3__T2   K3 + Port options (clause kept) + FIX1      cpu_regfile r0-r7
  P1t3__T3   K3 + K6 + SCOPE (no FIX1)                   cpu_regfile r0-r7
  P1t3__ALU  K3 (FIX2) + K6 (F1)                         cpu_alu r0-r3    <- stored P1diag__K3A2_K6 (only line 159 differs)
Readings (copied from CONFLICT_CLASSIFICATION.md before sending):
  cpu_regfile: a reply is broken when p1probe.p1_named finds 3 or more of ctrl_i.rf_rd, rf_rs1, rf_rs2, rf_wb_en,
    rf_zero_we and rf_we. Per reply also record whether "Not Kept" matches "access[- ]command|command[- ]field", and the
    number of concepts (and, added here, the cached input tokens).
    - Priority ambiguity is confirmed if T1 and T2 are each at 1 of 8 or fewer, while T0 and T3 are each at 3 of 8 or more.
    - It is refuted in favour of conditional conflict if T3 is at 1 of 8 or fewer while T1 is at 3 of 8 or more. The same
      holds if any broken reply in T1 or T2 cites Access command fields and still keeps the fields.
    - If T1 and T3 are both at 1 of 8 or fewer, both work by bringing the bar into view: the type stays undecided, and
      the shorter text should be adopted.
    - If T2 is at 3 of 8 or more while T1 is at 1 of 8 or fewer, the clause acts beyond priority, so also apply F1.
    - If T0 is at 1 of 8 or fewer, the background has gone (drift), and the test is inconclusive.
  cpu_alu:
    - R1 (fixed?): named (signal, repeat) pairs out of 20: 2 or fewer fixed; 6 or more not fixed; 3-5 no answer.
    - R2 (criterion taken up?): replies with any concept holding line 274 or 319 (A2 baseline 4 of 4): 1 of 4 or fewer
      taken up; 3 of 4 or more not taken up (the rule is not engaged in context; wording inside (a) will not fix it).
    - R3 (falsifies the classification): R2 at 1 of 4 or fewer but R1 at 6 or more -> the write-enable condition was not
      the cause; next candidate step 6.
    - R4 (second path): replies whose naming comes only from a concept held at port-map lines 258-261 / 301-304: 2 of 4
      or more -> that path needs its own fix.

  python -B p1test3.py selftest
  <conda python> p1test3.py run       (at most 36 new calls)
  python -B p1test3.py measure        (writes p1test3.json)
"""
import json
import os
import re
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import p1pairs as PP  # noqa: E402
import p1fixpair as FX  # noqa: E402
import p1diag2 as D2  # noqa: E402
import run_a  # noqa: E402

FIX1 = {7: ("such a decision is information of its own.",
            "such a decision is information of its own unless a rule's bar below covers it; check the bars before step 3 "
            "splits it or step 5 keeps it, and where one covers it, the bar decides (Precedence).")}
SCOPE = {158: ("or memory words (not a cache's copies).",
               "or memory words (not a cache's copies). The record port need not be a bus request record port: a processor's "
               "control record that names which of this unit's own registers a read or write reaches, and whether a write "
               "happens or is forced, carries such accesses; those register numbers are register-select address bits, not "
               "the access address of a memory's stored words.")}
NEW2 = {159: ("(2) a write enable whose assignment reads only these fields and that only lets a register or FIFO take the "
              "written data.",
              "(2) a write enable whose assignment reads only these fields and signals decoded from them (a select (b) keeps "
              "counts as one), and whose only use lets a register or FIFO take the written data, in this unit or at the "
              "write-enable input of an instance the access is passed on to (judge that input from its port name, and say so).")}
FIX2 = {**D2.A2, **NEW2}
REG, ALU = "neorv32_cpu_regfile", "neorv32_cpu_alu"
REGBARS = ["ctrl_i.rf_rd", "ctrl_i.rf_rs1", "ctrl_i.rf_rs2", "ctrl_i.rf_wb_en", "ctrl_i.rf_zero_we", "rf_we"]
NK = re.compile(r"access[- ]command|command[- ]field", re.I)


def specs():
    K = PP.clusters()
    return {
        "P1t3__T0": (K["K3"] + K["K6"], {}, REG, range(8)),
        "P1t3__T1": (K["K3"] + K["K6"], FIX1, REG, range(8)),
        "P1t3__T2": (K["K3"] + ["Port options"], FIX1, REG, range(8)),
        "P1t3__T3": (K["K3"] + K["K6"], SCOPE, REG, range(8)),
        "P1t3__ALU": (K["K3"] + K["K6"], {**FX.F1, **FIX2}, ALU, range(4)),
    }


def text_of(name):
    keep, fixes, _, _ = specs()[name]
    return FX.apply(P.build_keep(keep), fixes) if fixes else P.build_keep(keep)


def selftest(log=print):
    import check_new_rules as CN
    import meta_tools as mt
    checks = {}
    for name, (keep, fixes, m, reps) in specs().items():
        base = P.build_keep(keep).split(P.LF)
        t = text_of(name).split(P.LF)
        diff = [i for i, (a, b) in enumerate(zip(base, t)) if a != b]
        want = {FX.fixed_line(n, fixes) for n in fixes}
        checks[f"{name}: only the fixed lines differ"] = len(t) == len(base) and len(diff) == len(fixes) and all(t[i] in want for i in diff)
        active = {P.base_title(x) for _, _, x in P.blocks(t, t.index("OUTPUT"))}
        checks[f"{name}: active rules as planned"] = active == set(keep)
        log(f"{name}: {len(P.LF.join(t).split())} words; fixed lines {sorted(fixes)}; {m[8:]} x {len(list(reps))}")
    stored = (P.LAB / "prompts" / "diag_v10" / "P1pair__K3_K6" / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF)
    checks["T0 = the stored P1pair__K3_K6 prompt"] = text_of("P1t3__T0") == stored
    a = (P.LAB / "prompts" / "diag_v10" / "P1diag__K3A2_K6" / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF).split(P.LF)
    b = text_of("P1t3__ALU").split(P.LF)
    d = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    checks["ALU differs from P1diag__K3A2_K6 only at the criterion (2) line"] = len(a) == len(b) and len(d) == 1 and b[d[0]] == FX.fixed_line(159, NEW2)
    checks["the cpu_regfile bars are Access command fields' consistent bars"] = sorted(L.bars("P1-23 P2", [REG])[REG]) == sorted(REGBARS)
    blk = [FX.fixed_line(n, FIX2) if n in FIX2 else FX.V10P1[n - 1] for n in range(157, 169)]
    checks["FIX2 block passes check_new_rules"] = not CN.check_text("P1-23", "P1", P.LF.join(blk))
    blk3 = [FX.fixed_line(n, SCOPE) if n in SCOPE else FX.V10P1[n - 1] for n in range(157, 169)]
    checks["SCOPE block passes check_new_rules"] = not CN.check_text("P1-23", "P1", P.LF.join(blk3))
    checks["FIX1 line passes the prompt checks"] = not mt.check_prompt(FX.fixed_line(7, FIX1), CN.names(), "step 2")["problems"]
    bad = [k for k, v in checks.items() if not v]
    log(f"p1test3 self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def run():
    from concurrent.futures import ThreadPoolExecutor
    if not selftest():
        sys.exit("self-test FAIL; nothing sent")
    vers, calls, jobs = {}, {}, []
    stop = CH._new_run_flag()
    for name, (keep, fixes, m, reps) in specs().items():
        vers[name] = P.cell_version(name, text_of(name))
        L.track_folders([name])
    for rep in range(8):                                     # interleaved: repeat-major across the cells
        for name, (keep, fixes, m, reps) in specs().items():
            if rep not in reps:
                continue
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            if (name, rep) not in calls:
                calls[(name, rep)] = CH.openai(MODEL, EFFORT, out=out, poll=5)
            if not (out / "phase1" / f"{m}.json").exists():
                jobs.append((vers[name], m, out, calls[(name, rep)]))
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.02:.2f}); spent so far USD {spent:.2f}")
    if len(jobs) > 36:
        sys.exit("more than the 36 approved calls; nothing sent")

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
    out = {"regfile": {}, "alu": {}}
    broke = {}
    for name in ("P1t3__T0", "P1t3__T1", "P1t3__T2", "P1t3__T3"):
        rows = []
        for r in range(8):
            rec = json.loads((L.cell_dir(name, r) / "phase1" / f"{REG}.json").read_text(encoding="utf-8"))
            k = sum(P.p1_named(rec, REG, e) == "named" for e in REGBARS)
            nk = " ".join(json.dumps(x) for x in rec["reply"].get("considered, not kept") or [])
            rows.append({"rep": r, "named": k, "broken": k >= 3, "Not Kept access-command": bool(NK.search(nk)),
                         "cites the rule": bool(re.search(r"access command fields", rec.get("raw") or "", re.I)),
                         "concepts": len(rec["reply"]["conceptual assets"]), "cached": (rec.get("usage") or {}).get("cached")})
        broke[name] = sum(x["broken"] for x in rows)
        out["regfile"][name] = {"broken": f"{broke[name]}/8", "rows": rows}
        print(f"{name}: broken {broke[name]}/8  named {[x['named'] for x in rows]}  NotKept-access {[int(x['Not Kept access-command']) for x in rows]}  "
              f"concepts {[x['concepts'] for x in rows]}  cached {[x['cached'] for x in rows]}")
    t0, t1, t2, t3 = (broke[f"P1t3__T{i}"] for i in range(4))
    cites_kept = [f"{n} r{x['rep']}" for n in ("P1t3__T1", "P1t3__T2") for x in out["regfile"][n]["rows"] if x["broken"] and x["cites the rule"]]
    fired = []
    if t1 <= 1 and t2 <= 1 and t0 >= 3 and t3 >= 3:
        fired.append("priority ambiguity confirmed")
    if (t3 <= 1 and t1 >= 3) or cites_kept:
        fired.append("refuted in favour of conditional conflict" + (f" (broken replies citing the rule: {cites_kept})" if cites_kept else ""))
    if t1 <= 1 and t3 <= 1:
        fired.append("both work: type undecided, adopt the shorter text")
    if t2 >= 3 and t1 <= 1:
        fired.append("the clause acts beyond priority: also apply F1")
    if t0 <= 1:
        fired.append("T0 at 1 of 8 or fewer: drift, inconclusive")
    out["regfile"]["readings fired"] = fired or ["none of the pre-set readings fired"]
    print("cpu_regfile readings:", out["regfile"]["readings fired"])
    abars = sorted(L.bars("P1-23 P2", [ALU])[ALU])
    PM = set(range(258, 262)) | set(range(301, 305))
    SEL = {273, 274, 275, 318, 319, 320}
    named, r2, r4, per = 0, 0, 0, []
    for r in range(4):
        rec = json.loads((L.cell_dir("P1t3__ALU", r) / "phase1" / f"{ALU}.json").read_text(encoding="utf-8"))
        k = sum(P.p1_named(rec, ALU, e) == "named" for e in abars)
        cons = rec["reply"]["conceptual assets"]
        hold = any({274, 319} & set(c.get("held lines") or []) for c in cons)
        naming = [c for c in cons if set(abars) & set((c.get("enters through") or []) + (c.get("leaves through") or []))]
        only_pm = bool(naming) and all(set(c.get("held lines") or []) <= PM | set() and not (SEL & set(c.get("held lines") or [])) for c in naming)
        named += k
        r2 += hold
        r4 += only_pm
        per.append({"rep": r, "named": k, "holds 274/319": hold, "naming only from port-map concepts": only_pm,
                    "naming concepts": [(c.get("concept"), c.get("held lines")) for c in naming]})
    R1 = "fixed" if named <= 2 else "not fixed" if named >= 6 else "no answer"
    R2 = "taken up" if r2 <= 1 else "not taken up" if r2 >= 3 else "no answer"
    R3 = "the write-enable condition was not the cause" if (r2 <= 1 and named >= 6) else "does not fire"
    R4 = "the port-map path needs its own fix" if r4 >= 2 else "does not fire"
    out["alu"] = {"named": f"{named}/20", "R1": R1, "holds 274/319": f"{r2}/4", "R2": R2, "R3": R3,
                  "only port-map": f"{r4}/4", "R4": R4, "rows": per}
    print(f"cpu_alu: named {named}/20 -> R1 {R1}; holds 274/319 {r2}/4 -> R2 {R2}; R3 {R3}; only port-map {r4}/4 -> R4 {R4}")
    for x in per:
        print("   ", x["rep"], x["named"], x["holds 274/319"], x["naming concepts"])
    (HERE / "p1test3.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "run": run, "measure": measure}[sys.argv[1]]()
