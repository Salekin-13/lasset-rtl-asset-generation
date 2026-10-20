"""Rule-alone re-test of the Never-clause addition (PLAN_TIGHTEN2.md; user 2026-10-17: "Build stage 0 (v12u variant, self-tests,
cost preview), send all 102 requests in one batch with the readings in PLAN_TIGHTEN2.md, verify the readings independently,
and report."). Diagnostic only; the final Phase 1 prompt runs whole.

Wording: U = tighten2_P1-23.json (494 words) = the tightened wording (tighten_P1-23.json, 474) with its Never sentence
replaced. Rule-alone format (old reply format, max_tokens 64,000, clean background context_p1_v10u.md), luna, high.
Requests: v12u 41 modules x r0-r1 (82) + cpu, cache, cpu_lsu, cpu_frontend x r2-r5 (16); v12t control cpu_frontend x
r2-r5 (4). Total 102.
Readings (copied from PLAN_TIGHTEN2.md before sending). A reply bars a target when its barred list covers it (the target
or a record it is a field of). OVER[m] = signals barred in both v12c_new repeats and neither v12c_old repeat.
  U1 cpu, v12u r0-r5: no K07/K08 element or OVER[cpu] field barred: 0/6 -> out in every repeat; else not.
  U2 cache and cpu_lsu, v12u r0-r5 (12 replies), K09/K10 elements and their OVER fields: 0/12 -> out; 1/12 -> no answer;
     2/12 or more -> not. Comparator: v12t 4/12.
  U3 cpu_frontend ibus_rsp_i.ack, v12u r0-r5: barred in 0/6 -> fixed; 1/6 or more -> not. Control v12t r0-r5 reported.
  U4 cpu_icc icc_rx_i.ack barred in both v12u r0-r1; cpu_frontend ctrl_i.if_ack barred in at least 5 of 6 v12u r0-r5.
  U5 bus, xbus, cpu_control, v12u r0-r1: no K11-K13 element or OVER field barred in any of the 6 replies.
  U6 every K01, K02, K04, K05, K06a element barred in both v12u r0-r1; K03 kept (spared) in both.
  R1 against v12c_old: hard changes <= v12c_old's split signals (29) AND no bar change (barred in both repeats of one side,
     neither of the other) outside the intended list: cpu_control ctrl_o.csr_addr lost, cpu_icc icc_tx_o.ack lost,
     debug_dm auth.we added. New spared entries with no bar change are listed only.
  R2 no reference entry newly barred in both v12u repeats; R3 mean disagreement <= old + 0.05, contradiction modules <=
     old + 1; R4 cpu_alu fpu_csr_en / cfu_csr_en spared in both; cpu_regfile and cpu_alu consistent bars include v10's.
  Reported: bars v10 never makes (any repeat; v12t 6 signals / 7 events); barred-list splits over 41 (v12t 4, v10 11);
     hwspinlock bus_req_i.rw (v10 2/2, v12t 1/2).
  Adopt v12u in place of the tightened wording if U1-U6 and R1-R4 pass.

  python -B p1tighten2.py selftest
  python -B p1tighten2.py preview
  <conda python> p1tighten2.py run v12u    (cap 98)
  <conda python> p1tighten2.py run v12t    (cap 4; separate process: the isolation runner keeps one active variant)
  python -B p1tighten2.py measure          (writes p1tighten2.json)
"""
import json
import sys

import p1tighten as PT  # registers v12c_old / v12c_new / v12n / v12t; shares load(), covered()

ISO, CH, L, P, RB, AN, run_a = PT.ISO, PT.CH, PT.L, PT.P, PT.RB, PT.AN, PT.run_a
HERE, MODEL, EFFORT, REG, ALU, TIGHT = PT.HERE, PT.MODEL, PT.EFFORT, PT.REG, PT.ALU, PT.TIGHT
load, covered = PT.load, PT.covered
U = json.loads((HERE / "tighten2_P1-23.json").read_text(encoding="utf-8"))["P1-23"]["P1"].replace(P.CRLF, P.LF).strip().split(P.LF)
CASES = {c["id"]: c for c in json.loads((HERE / "tighten_cases.json").read_text(encoding="utf-8"))["cases"]}
ISO.VARIANTS["v12u"] = {"run": "rule_isolation_v12u", "texts": str(HERE / "rule_texts_v12u.json"),
                        "ctx": (str(HERE / "context_p1_v10u.md"), str(HERE / "context_p2_v10u.md"))}
CPU, CACHE, LSU, FE, ICC = "neorv32_cpu", "neorv32_cache", "neorv32_cpu_lsu", "neorv32_cpu_frontend", "neorv32_cpu_icc"
FOUR = [CPU, CACHE, LSU, FE]
SIX = ["neorv32_bus", CACHE, CPU, "neorv32_cpu_control", LSU, "neorv32_xbus"]
EXTRA = (2, 3, 4, 5)
CAP = {"v12u": 98, "v12t": 4}
OLD_NEVER = "Never a request leaving through an output port, even one this unit builds, nor a record one instance drives into other instances' port maps, nor any field of it."
NEW_NEVER = ("Never a request leaving through an output port for storage outside this unit, even one this unit builds, nor the command "
             "fields it is built from, nor the response coming back for it; nor a record one instance drives into other instances' port "
             "maps, nor any field of it.")
INTENDED = {("cpu_control", "ctrl_o.csr_addr", "lost"), ("cpu_icc", "icc_tx_o.ack", "lost"), ("debug_dm", "auth.we", "added")}


def write_texts():
    (HERE / "rule_texts_v12u.json").write_text(json.dumps(
        {"P1-23": {"title": "Access command fields", "P1": P.LF.join(U), "P2": None}}, indent=1, ensure_ascii=False), encoding="utf-8")


def jobs(var):
    ISO.use(var)
    if var == "v12u":
        jl, tx = ISO.jobs(None, reps=(0, 1), rules=["P1-23"], phases=("P1",))
        j2, _ = ISO.jobs(FOUR, reps=EXTRA, rules=["P1-23"], phases=("P1",))
        jl = jl + j2
    else:
        jl, tx = ISO.jobs([FE], reps=EXTRA, rules=["P1-23"], phases=("P1",))
    return jl, tx, [j for j in jl if not ISO.path(*j).exists()]


def selftest(log=print):
    import check_new_rules as CN
    write_texts()
    checks = {}
    diff = [i for i, (a, b) in enumerate(zip(TIGHT, U)) if a != b]
    checks["only the Never sentence differs from the tightened wording"] = (
        len(TIGHT) == len(U) and len(diff) == 1 and TIGHT[diff[0]].count(OLD_NEVER) == 1
        and U[diff[0]] == TIGHT[diff[0]].replace(OLD_NEVER, NEW_NEVER))
    checks["U block passes check_new_rules"] = not CN.check_text("P1-23", "P1", P.LF.join(U))
    checks["word count 494"] = len(P.LF.join(U).split()) == 494
    ISO.use("v12t")
    tt = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    ut = {m: ISO.user(m, "P1-23", "P1", tt) for m in (REG, ALU, CPU, FE)}
    st = CH.sha12(ISO.system("P1"))
    fe_stored = json.loads((ISO.run_root(rep=0) / "P1" / "P1-23" / f"{FE}.json").read_text(encoding="utf-8"))["user sha"]
    checks["v12t r2-r5 frontend request = its stored r0 request"] = CH.sha12(ut[FE]) == fe_stored
    ISO.use("v12u")
    tu = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    uu = {m: ISO.user(m, "P1-23", "P1", tu) for m in (REG, ALU, CPU, FE)}
    su = CH.sha12(ISO.system("P1"))
    ISO.use("v9")
    checks["v12u text = U"] = tu["P1-23"]["P1"] == P.LF.join(U)
    checks["v12u and v12t share the clean background"] = su == st
    checks["v12u request = v12t request with only the Never sentence swapped"] = all(
        uu[m].replace(NEW_NEVER, OLD_NEVER) == ut[m] and uu[m] != ut[m] for m in uu)
    checks["stored v12c_old, v12c_new, v12t r0-r1 complete (82 each)"] = all(
        len(list((P.LAB / "runs" / f"rule_isolation_{s}" / f"{MODEL}__{EFFORT}").glob("r[01]/P1/P1-23/*.json"))) == 82 for s in ("v12c_old", "v12c_new", "v12t"))
    checks["stored v12t r2-r5 for cpu, cache, cpu_lsu complete (12)"] = all(
        (P.LAB / "runs" / "rule_isolation_v12t" / f"{MODEL}__{EFFORT}" / f"r{r}" / "P1" / "P1-23" / f"{m}.json").exists() for r in EXTRA for m in (CPU, CACHE, LSU))
    checks["16 cases; K14 out, K15 in"] = len(CASES) == 16 and CASES["K14"]["expected"] == "out" and CASES["K15"]["expected"].startswith("in")
    bad = [k for k, v in checks.items() if not v]
    log(f"p1tighten2 self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def cost_of():
    per = {}
    for f in (P.LAB / "runs" / "rule_isolation_v12t" / f"{MODEL}__{EFFORT}").glob("r*/P1/P1-23/*.json"):
        per.setdefault(f.stem, []).append(run_a.usd(json.loads(f.read_text(encoding="utf-8"))["usage"]))
    return {m: sum(v) / len(v) for m, v in per.items()}


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    c = cost_of()
    n = tot = 0
    for var in ("v12u", "v12t"):
        jl, tx, todo = jobs(var)
        est = sum(c[j[2]] for j in todo)
        n += len(todo)
        tot += est
        print(f"{var}: {len(todo)} requests to send (of {len(jl)}), about USD {est:.2f} at v12t's per-module means")
        ISO.preview(todo, tx)
    ISO.use("v9")
    print(f"total {n} requests, about USD {tot:.2f}; spent so far USD {run_a.spent(log=lambda *a: None):.2f}")


def run(var):
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    jl, tx, todo = jobs(var)
    if len(todo) > CAP[var]:
        sys.exit(f"more than {CAP[var]} requests for {var}; nothing sent")
    tracked = [str(P.LAB / "runs" / ISO.VARIANTS[var]["run"] / f"{MODEL}__{EFFORT}")]
    ex = json.loads(L.EXTRA.read_text(encoding="utf-8")) if L.EXTRA.exists() else []
    L.EXTRA.write_text(json.dumps(ex + [p for p in tracked if p not in ex], indent=1), encoding="utf-8")
    print(f"{var}: sending {len(todo)}")
    ISO.run(todo, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=50)


def measure():
    import read_v11n as RV
    groups, refl = RB.CV.groups_and_ref()
    m41 = groups["tuning"] + groups["held-out"]
    old, short = load("v12c_old", m41, (0, 1)), load("v12c_new", m41, (0, 1))
    new = load("v12u", m41, (0, 1))
    new6 = load("v12u", FOUR, range(6))
    t6 = load("v12t", FOUR, range(6))
    OVER = {m: (AN.names(short[m][0], "barred") & AN.names(short[m][1], "barred")) - (AN.names(old[m][0], "barred") | AN.names(old[m][1], "barred")) for m in m41}
    K = lambda *ids: [e for i in ids for e in CASES[i]["elements"]]
    ids = {CPU: ("K07", "K08"), CACHE: ("K10",), LSU: ("K09",), "neorv32_bus": ("K12",), "neorv32_xbus": ("K13",), "neorv32_cpu_control": ("K11",)}

    def tally(data, mods):
        rows = []
        for m in mods:
            tg = set(K(*ids[m])) | OVER[m]
            for r, rep in enumerate(data[m]):
                rows.append({"module": m[8:], "rep": r, "applies": rep.get("applies") if isinstance(rep, dict) else None, "bars": covered(rep, tg)})
        return rows
    out = {}
    u1, u1t = tally(new6, [CPU]), tally(t6, [CPU])
    b1 = sum(bool(x["bars"]) for x in u1)
    out["U1"] = {"new": f"{b1}/6", "tight": f"{sum(bool(x['bars']) for x in u1t)}/6", "reading": "out in every repeat" if b1 == 0 else "not", "rows new": u1}
    u2, u2t = tally(new6, [CACHE, LSU]), tally(t6, [CACHE, LSU])
    b2 = sum(bool(x["bars"]) for x in u2)
    out["U2"] = {"new": f"{b2}/12", "tight": f"{sum(bool(x['bars']) for x in u2t)}/12", "reading": "out" if b2 == 0 else "no answer" if b2 == 1 else "not",
                 "rows new": u2, "rows tight": u2t}
    fe_new = [bool(covered(x, ["ibus_rsp_i.ack"])) for x in new6[FE]]
    fe_t = [bool(covered(x, ["ibus_rsp_i.ack"])) for x in t6[FE]]
    out["U3"] = {"new barred": f"{sum(fe_new)}/6", "tight barred": f"{sum(fe_t)}/6", "reading": "fixed" if sum(fe_new) == 0 else "not",
                 "per repeat new": fe_new, "per repeat tight": fe_t}
    icc = [bool(covered(x, ["icc_rx_i.ack"])) for x in new[ICC]]
    ifack = [bool(covered(x, ["ctrl_i.if_ack"])) for x in new6[FE]]
    out["U4"] = {"icc_rx_i.ack barred r0-r1": icc, "ctrl_i.if_ack barred r0-r5": ifack,
                 "ctrl_i.if_ack tight r0-r5": [bool(covered(x, ["ctrl_i.if_ack"])) for x in t6[FE]],
                 "pass": all(icc) and sum(ifack) >= 5}
    u5 = tally(new, ["neorv32_bus", "neorv32_xbus", "neorv32_cpu_control"])
    b5 = sum(bool(x["bars"]) for x in u5)
    out["U5"] = {"new": f"{b5}/6", "pass": b5 == 0, "rows": u5}
    u6 = {}
    for cid in ("K01", "K02", "K04", "K05", "K06a"):
        m = CASES[cid]["module"]
        u6[cid] = {e: sum(bool(covered(x, [e])) for x in new[m]) for e in CASES[cid]["elements"]}
    u6["K03 kept"] = {e: sum(isinstance(x, dict) and e in AN.names(x, "spared") for x in new[ALU]) for e in CASES["K03"]["elements"]}
    out["U6"] = {"repeats barring each element (of 2)": u6, "pass": all(v == 2 for d in u6.values() for v in d.values())}
    hard, split_old, newbar_ref, dis, contra, missing = [], 0, [], {"old": [], "new": []}, {"old": 0, "new": 0}, []
    for m in m41:
        o, n = old[m], new[m]
        if None in o or None in n or not all(isinstance(x, dict) for x in o + n):
            missing.append(m[8:])
            continue
        for key in ("barred", "spared"):
            O = [AN.names(x, key) for x in o]
            N = [AN.names(x, key) for x in n]
            split_old += len(O[0] ^ O[1])
            for e in sorted((O[0] & O[1]) - (N[0] | N[1])):
                hard.append({"module": m[8:], "signal": e, "list": key, "change": "lost" if key == "barred" else "spare lost"})
            for e in sorted((N[0] & N[1]) - (O[0] | O[1])):
                hard.append({"module": m[8:], "signal": e, "list": key, "change": "added" if key == "barred" else "spare added"})
        for e in refl.get(m, ()):
            if all(RB.down(e, AN.names(x, "barred")) for x in n) and not all(RB.down(e, AN.names(x, "barred")) for x in o):
                newbar_ref.append(f"{m[8:]}: {e}")
        for s, reps in (("old", o), ("new", n)):
            d, c, _, _ = RV.decide(reps, keep=False)
            if d is not None:
                dis[s].append(d)
            contra[s] += c
    for h in hard:
        h["intended"] = (h["module"], h["signal"], h["change"]) in INTENDED
    bar_changes = [h for h in hard if h["list"] == "barred"]
    unintended = [h for h in bar_changes if not h["intended"]]
    md = {s: round(sum(v) / len(v), 3) if v else 0.0 for s, v in dis.items()}
    keeps = all(isinstance(x, dict) and {"fpu_csr_en", "cfu_csr_en"} <= AN.names(x, "spared") for x in new[ALU])
    incl = {}
    for m in (REG, ALU):
        ob = AN.names(old[m][0], "barred") & AN.names(old[m][1], "barred")
        nb = AN.names(new[m][0], "barred") & AN.names(new[m][1], "barred")
        incl[m[8:]] = {"old": sorted(ob), "new": sorted(nb), "new includes old": ob <= nb}
    tight = load("v12t", m41, (0, 1))
    splits = {s: sum(len(AN.names(d[m][0], "barred") ^ AN.names(d[m][1], "barred")) for m in m41) for s, d in (("old", old), ("tight", tight), ("new", new))}

    def never(d_reps):
        sig, ev = set(), 0
        for m, reps in d_reps.items():
            ob = AN.names(old[m][0], "barred") | AN.names(old[m][1], "barred")
            for x in reps:
                for e in AN.names(x, "barred") if isinstance(x, dict) else ():
                    if not RB.down(e, ob) and (m[8:], e) != ("debug_dm", "auth.we"):
                        sig.add((m[8:], e))
                        ev += 1
        return sorted(sig), ev
    allnew = {m: new[m] + (new6[m][2:] if m in new6 else []) for m in m41}
    allt = {m: tight[m] + (t6[m][2:] if m in t6 else []) for m in m41}
    nv_new, ev_new = never(allnew)
    nv_t, ev_t = never(allt)
    hw = "neorv32_hwspinlock"
    out["rule-alone"] = {
        "replies missing or not parsed": missing,
        "R1 hard changes": len(hard), "R1 floor": split_old, "R1 bar changes": bar_changes, "R1 unintended bar changes": unintended,
        "R1 pass": len(hard) <= split_old and not unintended,
        "R2 reference newly barred in both repeats": newbar_ref, "R2 pass": not newbar_ref,
        "R3 mean disagreement old / new": [md["old"], md["new"]], "R3 contradiction modules old / new": [contra["old"], contra["new"]],
        "R3 pass": md["new"] <= md["old"] + 0.05 and contra["new"] <= contra["old"] + 1,
        "R4 cpu_alu selects kept": keeps, "R4 consistent bars": incl, "R4 pass": keeps and all(v["new includes old"] for v in incl.values()),
        "reported: bars v10 never makes (signals, events) new / tight": [[len(nv_new), ev_new], [len(nv_t), ev_t]],
        "reported: those signals, new": nv_new,
        "reported: barred-list splits over 41 old / tight / new": [splits["old"], splits["tight"], splits["new"]],
        "reported: hwspinlock bus_req_i.rw barred per repeat old / tight / new": [[bool(covered(x, ["bus_req_i.rw"])) for x in d[hw]] for d in (old, tight, new)],
        "spare-only changes": [h for h in hard if h["list"] == "spared"]}
    ra = out["rule-alone"]
    out["adopt v12u"] = (out["U1"]["reading"] == "out in every repeat" and out["U2"]["reading"] == "out" and out["U3"]["reading"] == "fixed"
                         and out["U4"]["pass"] and out["U5"]["pass"] and out["U6"]["pass"]
                         and ra["R1 pass"] and ra["R2 pass"] and ra["R3 pass"] and ra["R4 pass"])
    (HERE / "p1tighten2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k in ("U1", "U2", "U3", "U4", "U5"):
        print(k, {x: y for x, y in out[k].items() if not x.startswith("rows")})
        for row in out[k].get("rows new", out[k].get("rows", [])):
            if row["bars"]:
                print("   new", row)
    print("U6", json.dumps(out["U6"], ensure_ascii=False))
    print(json.dumps({k: v for k, v in ra.items() if k != "spare-only changes"}, indent=1, ensure_ascii=False))
    print("spare-only changes:", [(h["module"], h["signal"], h["change"]) for h in ra["spare-only changes"]])
    print("adopt v12u:", out["adopt v12u"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview, "run": lambda: run(sys.argv[2]),
     "measure": measure}[cmd]()
