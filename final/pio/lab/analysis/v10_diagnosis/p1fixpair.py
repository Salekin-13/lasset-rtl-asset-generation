"""Wording fixes for the Port options / Access command fields conflict and the cpu_alu breaks, tested in the cluster cells
again (user 2026-10-16: "after finding the causes, fix the wording of both ... & cpu_alu in the clustered prompt &
cluster test again"). Diagnostic cells only; the final Phase 1 prompt runs whole.

Causes found (D45 and this round, read-only):
  - cpu_regfile: Port options' clause "although step 2 names each enable, step 3 splits by use and it gates an output
    port" (v10 phase1.md:141) makes the model split the register selects and write enables into pieces (removed: 4/22).
  - cpu_alu: in all 35 stored concepts naming the CSR fields, the piece is the read select that Access command fields (b)
    allows (held at lines 273/275/318/320); the model lists the fields it is decoded from under "Enters Through", and in
    32 of 35 also cites the write-enable lines 274/319 that (a) bars. (a) never says "not under Enters Through"; (b) gives
    no anchoring beyond "hold it at the line assigning it".
Fixes (exact line replacements in v10 phase1.md; checked by check_new_rules.py's prompt checks):
  F1 Port options, line 141: drop the clause above.
  A1 Access command fields, line 162: "Evidence: do not list them under "Enters Through", and cite no line ..." (as
     Operation selectors' Evidence, line 151); line 168: "Evidence: hold it at the line assigning it; list none of the
     fields it is decoded from under "Enters Through", and cite no line (a) bars as its held line." (step 6: "Skip ports
     that only decide the information").
Cells (luna, high, v10's own Phase 1 format) and their stored OLD counterparts:
  P1fix__PO_alone   core + Port options (F1)          sdi, uart r0-r1          <- P1alone__P118__K6
  P1fix__K6         core + K6 (F1)                    sdi, uart r0-r1          <- P1cluster__K6
  P1fix__ACF_alone  core + Access command fields (A1) cpu_regfile, cpu_alu, cpu_pmp, debug_dm, imem r0-r1
                                                      <- P123__P1_S1 (regfile, alu), P1alone__P123__K3 (pmp, dm, imem)
  P1fix__K3         core + K3 (A1)                    the same 5 modules r0-r1 <- P1cluster__K3
  P1fix__K3_K6      core + K3 (A1) + K6 (F1)          cpu_regfile, cpu_alu r0-r3 <- P1pair__K3_K6
Measures: a bar rule's consistent rule-alone Phase 1 bars (p1clusters.decisions) that Phase 1 names (p1probe.p1_named);
  recall guard: reference signals of the module that Phase 1 names or line-links.
Readings (set 2026-10-16 before sending):
  R1 Port options keeps its own bars without the clause: in P1fix__PO_alone and P1fix__K6, the share of its bars not
     named is not below the OLD cell's by more than 0.15 (chosen) -> keeps; else -> the clause is needed (next: a
     narrower rewording).
  R2 A1 removes the cpu_alu breaks: P1fix__K3_K6 cpu_alu, r0-r3 (20 pairs): 2/20 or fewer named -> fixed; 6/20 or more
     -> not fixed; 3-5 -> no answer (OLD 9/20).
  R3 The conflict is gone: P1fix__K3_K6 all pairs r0-r3 (44): 10/44 or fewer named -> removed; 24/44 or more -> still
     there; 11-23 -> no answer (OLD 24/44; K3 alone 6/44).
  R4 No harm elsewhere: in P1fix__ACF_alone and P1fix__K3, per module, named pairs not above OLD by more than 2
     (chosen), and the recall guard not below OLD by more than 0.05 (chosen).
Resolution: about 2 replies per module per cell (4 for the r0-r3 pair cell).

  python -B p1fixpair.py selftest
  <conda python> p1fixpair.py run     (at most 36 new calls)
  python -B p1fixpair.py measure      (writes p1fixpair.json)
"""
import json
import os
import sys
import threading

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import p1clusters as PC  # noqa: E402
import p1pairs as PP  # noqa: E402
import rule_breaks as RB  # noqa: E402
import run_a  # noqa: E402

V10P1 = P.V10D.joinpath("phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF).split(P.LF)
F1 = {141: (", although step 2 names each enable, step 3 splits by use and it gates an output port", "")}
A1 = {162: ("  Evidence: cite no line only testing them,",
            '  Evidence: do not list them under "Enters Through", and cite no line only testing them,'),
      168: ("  Evidence: hold it at the line assigning it.",
            '  Evidence: hold it at the line assigning it; list none of the fields it is decoded from under "Enters Through", '
            'and cite no line (a) bars as its held line.')}
FIVE = ["neorv32_cpu_regfile", "neorv32_cpu_alu", "neorv32_cpu_pmp", "neorv32_debug_dm", "neorv32_imem"]
K6M = ["neorv32_sdi", "neorv32_uart"]


def fixed_line(n, fixes):
    old, new = fixes[n]
    assert V10P1[n - 1].count(old) == 1, n
    return V10P1[n - 1].replace(old, new, 1)


def apply(text, fixes):
    out = text.split(P.LF)
    for n in fixes:
        i = [k for k, l in enumerate(out) if l == V10P1[n - 1]]
        assert len(i) == 1, (n, len(i))
        out[i[0]] = fixed_line(n, fixes)
    return P.LF.join(out)


def cell_specs():
    K = PP.clusters()
    return {
        "P1fix__PO_alone": (["Port options"], F1, K6M, (0, 1), {m: "P1alone__P118__K6" for m in K6M}),
        "P1fix__K6": (K["K6"], F1, K6M, (0, 1), {m: "P1cluster__K6" for m in K6M}),
        "P1fix__ACF_alone": (["Access command fields"], A1, FIVE, (0, 1),
                             {m: ("P123__P1_S1" if m in FIVE[:2] else "P1alone__P123__K3") for m in FIVE}),
        "P1fix__K3": (K["K3"], A1, FIVE, (0, 1), {m: "P1cluster__K3" for m in FIVE}),
        "P1fix__K3_K6": (K["K3"] + K["K6"], {**F1, **A1}, FIVE[:2], (0, 1, 2, 3), {m: "P1pair__K3_K6" for m in FIVE[:2]}),
    }


def text_of(name):
    keep, fixes, _, _, _ = cell_specs()[name]
    return apply(P.build_keep(keep), fixes)


def selftest(log=print):
    checks = {}
    for name, (keep, fixes, mods, reps, old) in cell_specs().items():
        base = P.build_keep(keep).split(P.LF)
        t = text_of(name).split(P.LF)
        diff = [i for i, (a, b) in enumerate(zip(base, t)) if a != b]
        checks[f"{name}: only the fixed lines differ"] = len(t) == len(base) and len(diff) == len(fixes)
        checks[f"{name}: each fixed line = the v10 line with the stated words changed"] = all(
            t[i] in {fixed_line(n, fixes) for n in fixes} for i in diff)
        active = {P.base_title(x) for _, _, x in P.blocks(t, t.index("OUTPUT"))}
        checks[f"{name}: active rules as planned"] = active == set(keep)
        for m in mods:
            o = old[m]
            ok = all((L.cell_dir(o, r) / "phase1" / f"{m}.json").exists() for r in reps)
            checks[f"{name}: OLD {o} has {m[8:]} for every repeat"] = ok
        log(f"{name}: {len(P.LF.join(t).split())} words (OLD text {len(P.LF.join(base).split())}); modules {[m[8:] for m in mods]}; repeats {reps}")
    # the fixed rule texts pass the project's prompt checks (corpus names, numeric hints)
    import check_new_rules as CN
    for rid, title, fixes in (("P1-18", "Port options", F1), ("P1-23", "Access command fields", A1)):
        blk = [fixed_line(n, fixes) if n in fixes else V10P1[n - 1] for a, b, t in P.blocks(V10P1, V10P1.index("OUTPUT"))
               if P.base_title(t) == title for n in range(a + 1, b + 1)]
        probs = CN.check_text(rid, "P1", P.LF.join(blk))
        checks[f"{title} fixed text passes check_new_rules ({len(P.LF.join(blk).split())} words)"] = not probs
    bad = [k for k, v in checks.items() if not v]
    log(f"p1fixpair self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def run():
    from concurrent.futures import ThreadPoolExecutor
    if not selftest():
        sys.exit("self-test FAIL; nothing sent")
    jobs, stop = [], CH._new_run_flag()
    for name, (keep, fixes, mods, reps, old) in cell_specs().items():
        v = P.cell_version(name, text_of(name))
        L.track_folders([name])
        for rep in reps:
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            call = CH.openai(MODEL, EFFORT, out=out, poll=5)
            jobs += [(v, m, out, call) for m in mods if not (out / "phase1" / f"{m}.json").exists()]
    spent = run_a.spent(log=lambda *a: None)
    print(f"{len(jobs)} calls to send (about USD {len(jobs) * 0.022:.2f}); spent so far USD {spent:.2f}")
    if len(jobs) > 36:
        sys.exit("more than the 36 planned calls; nothing sent")

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
    mods41 = groups["tuning"] + groups["held-out"]
    dec = PC.decisions(mods41)
    rid = {"Port options": "P1-18", "Access command fields": "P1-23"}
    out = {}

    def score(cell, m, reps, bars):
        named = guard = n = 0
        ref = sorted(refl.get(m, ()))
        for r in reps:
            rec = json.loads((L.cell_dir(cell, r) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
            named += sum(P.p1_named(rec, m, e) == "named" for e in bars)
            guard += sum(P.p1_named(rec, m, e) != "not in Phase 1" for e in ref)
            n += len(ref)
        return named, len(bars) * len(reps), (guard / n if n else None)
    for name, (keep, fixes, mods, reps, old) in cell_specs().items():
        rules = ["Port options"] if fixes is F1 else ["Access command fields"] if fixes is A1 else ["Access command fields"]
        for title in rules:
            for m in mods:
                bars = sorted(dec[rid[title]].get(m, ()))
                nn, pairs, gn = score(name, m, reps, bars)
                on, _, go = score(old[m], m, reps, bars)
                key = f"{name} | {title} | {m[8:]}"
                out[key] = {"NEW named": nn, "OLD named": on, "pairs": pairs, "NEW guard": gn, "OLD guard": go, "OLD cell": old[m]}
                print(f"{key:60s} named NEW {nn:2d} / OLD {on:2d} of {pairs:2d} | reference named or linked NEW "
                      f"{gn:.2f} / OLD {go:.2f}")
    # readings
    def tot(prefix, title, key):
        return sum(v[key] for k, v in out.items() if k.startswith(prefix) and f"| {title} |" in k)
    r1 = {}
    for cell in ("P1fix__PO_alone", "P1fix__K6"):
        nn, on = tot(cell, "Port options", "NEW named"), tot(cell, "Port options", "OLD named")
        pairs = tot(cell, "Port options", "pairs")
        r1[cell] = ("keeps" if (1 - nn / pairs) >= (1 - on / pairs) - 0.15 else "loses") + f" (named NEW {nn} / OLD {on} of {pairs})"
    alu = out["P1fix__K3_K6 | Access command fields | cpu_alu"]["NEW named"]
    allp = tot("P1fix__K3_K6", "Access command fields", "NEW named")
    r2 = "fixed" if alu <= 2 else "not fixed" if alu >= 6 else "no answer"
    r3 = "removed" if allp <= 10 else "still there" if allp >= 24 else "no answer"
    harm = [k for k, v in out.items() if k.split(" | ")[0] in ("P1fix__ACF_alone", "P1fix__K3")
            and (v["NEW named"] > v["OLD named"] + 2 or (v["NEW guard"] is not None and v["NEW guard"] < v["OLD guard"] - 0.05))]
    out["readings"] = {"R1 Port options keeps its bars": r1, "R2 cpu_alu": f"{r2} ({alu}/20)", "R3 conflict": f"{r3} ({allp}/44)",
                       "R4 harm (cells over the cuts)": harm or "none"}
    print(json.dumps(out["readings"], indent=1))
    (HERE / "p1fixpair.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "run": run, "measure": measure}[sys.argv[1]]()
