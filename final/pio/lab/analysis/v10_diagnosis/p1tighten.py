"""Rule-alone re-test of the tightened Access command fields scope (PLAN_TIGHTEN.md; user 2026-10-17: "Re-judge the repaired
text with two blind judges first, then build stage 0 (v12t variant, self-tests, cost preview), send all 106 requests in one
batch with the readings in PLAN_TIGHTEN.md, and report."). Diagnostic only; the final Phase 1 prompt runs whole.

Wording: TIGHT = tighten_P1-23.json (474 words) = the narrow wording (narrow_P1-23.json, 432) with part (a)'s Scope line
replaced. Rule-alone format (old reply format, max_tokens 64,000, clean background context_p1_v10u.md), luna, high.
Requests: v12t 41 modules x r0-r1 (82) + cpu, cache, cpu_lsu x r2-r5 (12); v12n (narrow) control cpu, cache, cpu_lsu x
r2-r5 (12). Total 106.
Readings (copied from PLAN_TIGHTEN.md before sending). A reply "bars" a target when its barred list covers it (the target or
a record it is a field of; rule_breaks.down). OVER[m] = signals barred in both v12c_new (short) repeats and in neither
v12c_old (v10) repeat.
  T1 cpu: v12t r0-r5, replies barring any K07 or K08 element or any OVER[cpu] signal: 0/6 -> out in every repeat;
     1/6 or more -> not. Control v12n r0-r5 reported.
  T2 cache and cpu_lsu: v12t r0-r5 (12 replies) barring any K09 or K10 element or their OVER signals: 0/12 -> out;
     1/12 -> no answer; 2/12 or more -> not. Control v12n reported.
  T3 bus, xbus, cpu_control: v12t r0-r1, no K11-K13 element or OVER signal barred in any of the 6 replies.
  T4 every K01, K02, K04, K05, K06a element barred in both v12t r0-r1 repeats; K03 kept (spared) in both.
  R1-R4 against v12c_old as in D52: R1 hard changes <= v12c_old's split signals (29), listed and marked intended (removed:
     cpu_control ctrl_o.csr_addr, cpu_icc icc_tx_o.ack; added: debug_dm auth.we) or not; R2 no reference entry newly
     barred in both repeats; R3 mean disagreement <= old + 0.05 and contradiction modules <= old + 1; R4 cpu_alu
     fpu_csr_en / cfu_csr_en spared in both, cpu_regfile and cpu_alu consistent bars include v10's.
  Reported, no pass rule: barred-list split signals over 41 modules (v10 11, narrow 23); one-repeat OVER bars in the six
     over-reach modules (narrow 17).
  Adopt TIGHT in place of the narrow wording if T1-T4 and R1-R4 pass.

  python -B p1tighten.py selftest
  python -B p1tighten.py preview
  <conda python> p1tighten.py run v12t     (cap 94)
  <conda python> p1tighten.py run v12n     (cap 12; separate process: the isolation runner keeps one active variant)
  python -B p1tighten.py measure           (writes p1tighten.json)
"""
import json
import sys

import p1narrow as PN  # registers v12c_old / v12c_new / v12n

ISO, CH, L, P, RB, AN, run_a = PN.ISO, PN.CH, PN.L, PN.P, PN.RB, PN.AN, PN.run_a
HERE, MODEL, EFFORT, REG, ALU, NARROW = PN.HERE, PN.MODEL, PN.EFFORT, PN.REG, PN.ALU, PN.NARROW
TIGHT = json.loads((HERE / "tighten_P1-23.json").read_text(encoding="utf-8"))["P1-23"]["P1"].replace(P.CRLF, P.LF).strip().split(P.LF)
CASES = {c["id"]: c for c in json.loads((HERE / "tighten_cases.json").read_text(encoding="utf-8"))["cases"]}
ISO.VARIANTS["v12t"] = {"run": "rule_isolation_v12t", "texts": str(HERE / "rule_texts_v12t.json"),
                        "ctx": (str(HERE / "context_p1_v10u.md"), str(HERE / "context_p2_v10u.md"))}
CPU, CACHE, LSU = "neorv32_cpu", "neorv32_cache", "neorv32_cpu_lsu"
THREE = [CPU, CACHE, LSU]
SIX = ["neorv32_bus", CACHE, CPU, "neorv32_cpu_control", LSU, "neorv32_xbus"]
EXTRA = (2, 3, 4, 5)
CAP = {"v12t": 94, "v12n": 12}
INTENDED = {("cpu_control", "ctrl_o.csr_addr", "barred both old, neither tight"), ("cpu_icc", "icc_tx_o.ack", "barred both old, neither tight"),
            ("debug_dm", "auth.we", "barred both tight, neither old")}


def write_texts():
    (HERE / "rule_texts_v12t.json").write_text(json.dumps(
        {"P1-23": {"title": "Access command fields", "P1": P.LF.join(TIGHT), "P2": None}}, indent=1, ensure_ascii=False), encoding="utf-8")


def mods41():
    g, _ = RB.CV.groups_and_ref()
    return g["tuning"] + g["held-out"]


def jobs(var):
    ISO.use(var)
    if var == "v12t":
        jl, tx = ISO.jobs(None, reps=(0, 1), rules=["P1-23"], phases=("P1",))
        j2, _ = ISO.jobs(THREE, reps=EXTRA, rules=["P1-23"], phases=("P1",))
        jl = jl + j2
    else:
        jl, tx = ISO.jobs(THREE, reps=EXTRA, rules=["P1-23"], phases=("P1",))
    return jl, tx, [j for j in jl if not ISO.path(*j).exists()]


def selftest(log=print):
    import check_new_rules as CN
    write_texts()
    checks = {}
    nl, tl = NARROW, TIGHT
    diff = [i for i, (a, b) in enumerate(zip(nl, tl)) if a != b]
    checks["only part (a)'s Scope line differs from the narrow wording"] = len(nl) == len(tl) and len(diff) == 1 and tl[diff[0]].startswith("  Scope: Accesses ending in")
    checks["TIGHT block passes check_new_rules"] = not CN.check_text("P1-23", "P1", P.LF.join(TIGHT))
    checks["word count 474"] = len(P.LF.join(TIGHT).split()) == 474
    ISO.use("v12n")
    tn = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    un = {m: ISO.user(m, "P1-23", "P1", tn) for m in (REG, ALU, CPU)}
    sn = CH.sha12(ISO.system("P1"))
    stored = {m: json.loads((ISO.run_root(rep=0) / "P1" / "P1-23" / f"{m}.json").read_text(encoding="utf-8"))["user sha"] for m in THREE}
    checks["v12n r2-r5 requests = its stored r0 requests (cpu, cache, cpu_lsu)"] = all(
        CH.sha12(ISO.user(m, "P1-23", "P1", tn)) == stored[m] for m in THREE)
    ISO.use("v12t")
    tt = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    ut = {m: ISO.user(m, "P1-23", "P1", tt) for m in (REG, ALU, CPU)}
    st = CH.sha12(ISO.system("P1"))
    ISO.use("v9")
    checks["v12t text = TIGHT"] = tt["P1-23"]["P1"] == P.LF.join(TIGHT)
    checks["v12t and v12n share the clean background"] = st == sn
    checks["v12t request = v12n request with only the Scope line swapped"] = all(
        ut[m].replace(tl[diff[0]], nl[diff[0]]) == un[m] and ut[m] != un[m] for m in (REG, ALU, CPU)) if len(diff) == 1 else False
    checks["stored v12c_old, v12c_new, v12n r0-r1 complete (82 each)"] = all(
        len(list((P.LAB / "runs" / f"rule_isolation_{s}" / f"{MODEL}__{EFFORT}").glob("r[01]/P1/P1-23/*.json"))) == 82 for s in ("v12c_old", "v12c_new", "v12n"))
    checks["cases K01-K13 with K06 split into K06a / K06b"] = sorted(CASES) == sorted(["K01", "K02", "K03", "K04", "K05", "K06a", "K06b", "K07", "K08", "K09", "K10", "K11", "K12", "K13"])
    checks["K06b expected out, K06a in"] = CASES["K06b"]["expected"] == "out" and CASES["K06a"]["expected"].startswith("in")
    bad = [k for k, v in checks.items() if not v]
    log(f"p1tighten self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def cost_of():
    import run_a as RA
    per = {}
    for f in (P.LAB / "runs" / "rule_isolation_v12n" / f"{MODEL}__{EFFORT}").glob("r[01]/P1/P1-23/*.json"):
        per.setdefault(f.stem, []).append(RA.usd(json.loads(f.read_text(encoding="utf-8"))["usage"]))
    return {m: sum(v) / len(v) for m, v in per.items()}


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    c = cost_of()
    tot_n = tot_c = 0
    for var in ("v12t", "v12n"):
        jl, tx, todo = jobs(var)
        est = sum(c[j[2]] for j in todo)
        tot_n += len(todo)
        tot_c += est
        print(f"{var}: {len(todo)} requests to send (of {len(jl)}), about USD {est:.2f} at v12n's per-module means")
        ISO.preview(todo, tx)
    ISO.use("v9")
    print(f"total {tot_n} requests, about USD {tot_c:.2f}; spent so far USD {run_a.spent(log=lambda *a: None):.2f}")


def run(var):
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    jl, tx, todo = jobs(var)
    if len(todo) > CAP[var]:
        sys.exit(f"more than {CAP[var]} requests for {var}; nothing sent")
    for r in sorted({j[3] for j in todo}):
        ISO.run_root(rep=r).mkdir(parents=True, exist_ok=True)
    tracked = [str(P.LAB / "runs" / ISO.VARIANTS[var]["run"] / f"{MODEL}__{EFFORT}")]
    ex = json.loads(L.EXTRA.read_text(encoding="utf-8")) if L.EXTRA.exists() else []
    L.EXTRA.write_text(json.dumps(ex + [p for p in tracked if p not in ex], indent=1), encoding="utf-8")
    print(f"{var}: sending {len(todo)}")
    ISO.run(todo, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=48)


def load(var, mods, reps):
    ISO.use(var)
    out = {m: [json.loads((ISO.run_root(rep=r) / "P1" / "P1-23" / f"{m}.json").read_text(encoding="utf-8")).get("reply")
               if (ISO.run_root(rep=r) / "P1" / "P1-23" / f"{m}.json").exists() else None for r in reps] for m in mods}
    ISO.use("v9")
    return out


def covered(reply, targets):
    b = AN.names(reply, "barred") if isinstance(reply, dict) else set()
    return sorted(e for e in targets if RB.down(e, b))


def measure():
    import read_v11n as RV
    from collections import Counter
    groups, refl = RB.CV.groups_and_ref()
    m41 = groups["tuning"] + groups["held-out"]
    old, short = load("v12c_old", m41, (0, 1)), load("v12c_new", m41, (0, 1))
    tight = load("v12t", m41, (0, 1))
    t6 = load("v12t", THREE, range(6))
    n6 = load("v12n", THREE, range(6))
    OVER = {m: (AN.names(short[m][0], "barred") & AN.names(short[m][1], "barred")) - (AN.names(old[m][0], "barred") | AN.names(old[m][1], "barred")) for m in m41}
    K = lambda *ids: [e for i in ids for e in CASES[i]["elements"]]
    out = {"OVER sizes": {m[8:]: len(OVER[m]) for m in SIX}}

    def tally(data, mods, ids):
        rows = []
        for m in mods:
            tg = set(K(*ids[m])) | OVER[m]
            for r, rep in enumerate(data[m]):
                hit = covered(rep, tg)
                rows.append({"module": m[8:], "rep": r, "applies": rep.get("applies") if isinstance(rep, dict) else None, "bars": hit})
        return rows
    ids = {CPU: ("K07", "K08"), CACHE: ("K10",), LSU: ("K09",), "neorv32_bus": ("K12",), "neorv32_xbus": ("K13",), "neorv32_cpu_control": ("K11",)}
    t1 = tally(t6, [CPU], ids)
    t1n = tally(n6, [CPU], ids)
    b1 = sum(bool(x["bars"]) for x in t1)
    out["T1"] = {"tight replies barring": f"{b1}/{len(t1)}", "control narrow": f"{sum(bool(x['bars']) for x in t1n)}/{len(t1n)}",
                 "reading": "out in every repeat" if b1 == 0 else "not", "rows tight": t1, "rows narrow": t1n}
    t2 = tally(t6, [CACHE, LSU], ids)
    t2n = tally(n6, [CACHE, LSU], ids)
    b2 = sum(bool(x["bars"]) for x in t2)
    out["T2"] = {"tight replies barring": f"{b2}/{len(t2)}", "control narrow": f"{sum(bool(x['bars']) for x in t2n)}/{len(t2n)}",
                 "reading": "out" if b2 == 0 else "no answer" if b2 == 1 else "not", "rows tight": t2, "rows narrow": t2n}
    t3 = tally(tight, ["neorv32_bus", "neorv32_xbus", "neorv32_cpu_control"], ids)
    b3 = sum(bool(x["bars"]) for x in t3)
    out["T3"] = {"tight replies barring": f"{b3}/{len(t3)}", "pass": b3 == 0, "rows": t3}
    t4 = {}
    for cid in ("K01", "K02", "K04", "K05", "K06a"):
        m = CASES[cid]["module"]
        t4[cid] = {e: sum(bool(covered(x, [e])) for x in tight[m]) for e in CASES[cid]["elements"]}
    k3 = {e: sum(isinstance(x, dict) and e in AN.names(x, "spared") for x in tight[ALU]) for e in CASES["K03"]["elements"]}
    t4["K03 kept"] = k3
    out["T4"] = {"repeats barring each element (of 2)": t4,
                 "pass": all(v == 2 for cid, d in t4.items() for v in d.values())}
    hard, split_old, newbar_ref, dis, contra, missing = [], 0, [], {"old": [], "tight": []}, {"old": 0, "tight": 0}, []
    for m in m41:
        o, n = old[m], tight[m]
        if None in o or None in n or not all(isinstance(x, dict) for x in o + n):
            missing.append(m[8:])
            continue
        for key in ("barred", "spared"):
            O = [AN.names(x, key) for x in o]
            N = [AN.names(x, key) for x in n]
            split_old += len(O[0] ^ O[1])
            for e in sorted((O[0] & O[1]) - (N[0] | N[1])):
                hard.append({"module": m[8:], "signal": e, "change": f"{key} both old, neither tight"})
            for e in sorted((N[0] & N[1]) - (O[0] | O[1])):
                hard.append({"module": m[8:], "signal": e, "change": f"{key} both tight, neither old"})
        for e in refl.get(m, ()):
            if all(RB.down(e, AN.names(x, "barred")) for x in n) and not all(RB.down(e, AN.names(x, "barred")) for x in o):
                newbar_ref.append(f"{m[8:]}: {e}")
        for s, reps in (("old", o), ("tight", n)):
            d, c, _, _ = RV.decide(reps, keep=False)
            if d is not None:
                dis[s].append(d)
            contra[s] += c
    for h in hard:
        h["intended"] = (h["module"], h["signal"], h["change"]) in INTENDED
    md = {s: round(sum(v) / len(v), 3) if v else 0.0 for s, v in dis.items()}
    keeps = all(isinstance(x, dict) and {"fpu_csr_en", "cfu_csr_en"} <= AN.names(x, "spared") for x in tight[ALU])
    incl = {}
    for m in (REG, ALU):
        ob = AN.names(old[m][0], "barred") & AN.names(old[m][1], "barred")
        nb = AN.names(tight[m][0], "barred") & AN.names(tight[m][1], "barred")
        incl[m[8:]] = {"old": sorted(ob), "tight": sorted(nb), "tight includes old": ob <= nb}
    splits = {s: sum(len(AN.names(d[m][0], "barred") ^ AN.names(d[m][1], "barred")) for m in m41)
              for s, d in (("old", old), ("narrow", load("v12n", m41, (0, 1))), ("tight", tight))}
    one_rep = {m[8:]: sorted(e for e in OVER[m] if bool(covered(tight[m][0], [e])) != bool(covered(tight[m][1], [e]))) for m in SIX}
    out["rule-alone"] = {
        "replies missing or not parsed": missing,
        "R1 hard changes": len(hard), "R1 floor": split_old, "R1 not intended": [h for h in hard if not h["intended"]],
        "R1 pass": len(hard) <= split_old,
        "R2 reference newly barred in both repeats": newbar_ref, "R2 pass": not newbar_ref,
        "R3 mean disagreement old / tight": [md["old"], md["tight"]], "R3 contradiction modules old / tight": [contra["old"], contra["tight"]],
        "R3 pass": md["tight"] <= md["old"] + 0.05 and contra["tight"] <= contra["old"] + 1,
        "R4 cpu_alu selects kept": keeps, "R4 consistent bars": incl, "R4 pass": keeps and all(v["tight includes old"] for v in incl.values()),
        "reported: barred-list splits over 41 old / narrow / tight": [splits["old"], splits["narrow"], splits["tight"]],
        "reported: one-repeat OVER bars in the six modules, tight r0-r1": {k: v for k, v in one_rep.items() if v},
        "reported: one-repeat OVER bars total": sum(len(v) for v in one_rep.values()),
        "reported: applies per repeat r0-r1 old / tight": {m[8:]: [[x.get("applies") for x in old[m]], [x.get("applies") for x in tight[m]]] for m in SIX},
        "hard changes": hard}
    ra = out["rule-alone"]
    out["adopt tight"] = (out["T1"]["reading"] == "out in every repeat" and out["T2"]["reading"] == "out" and out["T3"]["pass"]
                          and out["T4"]["pass"] and ra["R1 pass"] and ra["R2 pass"] and ra["R3 pass"] and ra["R4 pass"])
    (HERE / "p1tighten.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k in ("T1", "T2", "T3"):
        print(k, {x: y for x, y in out[k].items() if not x.startswith("rows")})
        for row in out[k].get("rows tight", out[k].get("rows", [])):
            if row["bars"]:
                print("   tight", row)
    print("T4", json.dumps(out["T4"], ensure_ascii=False))
    print(json.dumps({k: v for k, v in ra.items() if k != "hard changes"}, indent=1, ensure_ascii=False))
    for h in ra["hard changes"]:
        print(f"  {h['module']}: {h['signal']} ({h['change']}){'  intended' if h['intended'] else ''}")
    print("adopt tight:", out["adopt tight"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview, "run": lambda: run(sys.argv[2]),
     "measure": measure}[cmd]()
