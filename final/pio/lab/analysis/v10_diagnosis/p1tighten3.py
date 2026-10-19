"""Targeted rule-alone re-test of round 3 ("This rule does not cover" in place of "Never"; PLAN_TIGHTEN3.md; user 2026-10-17:
"Build stage 0 (v12v variant, self-tests, cost preview), send all 52 requests in one batch with the readings in
PLAN_TIGHTEN3.md, verify the readings independently, and report."). Diagnostic only; the final Phase 1 prompt runs whole.

Wording: V = tighten3_P1-23.json (498 words) = round 2 (tighten2_P1-23.json, 494) with "Never" replaced by "This rule does
not cover". Rule-alone format (old reply format, max_tokens 64,000, clean background context_p1_v10u.md), luna, high.
Requests: v12v cpu_lsu, cpu_frontend, cpu_icc, cpu_control x r0-r5 (24); cpu, cache x r0-r3 (8); cpu_regfile, cpu_alu,
debug_dm, uart, bus, xbus x r0-r1 (12); v12u control cpu_icc, cpu_control x r2-r5 (8). Total 52.
Readings (copied from PLAN_TIGHTEN3.md before sending). A reply bars a target when its barred list covers it. Targets as in
PLAN_TIGHTEN2.md (case elements; OVER[m] = barred in both v12c_new repeats and neither v12c_old repeat).
  V1 inversion: barred entries whose "rule words" quote the sentence (any of the PHRASES below): 0 of 44 v12v replies ->
     pass; else fail. Round 2: 1 of 98.
  V2 cpu_frontend ibus_rsp_i.ack barred in 0 of 6 -> pass.
  V3 cpu_lsu r0-r5 and cache r0-r3 (10 replies), K09/K10 elements and their OVER fields: 0/10 -> out; 1/10 -> no answer;
     2/10 or more -> not.
  V4 cpu_icc icc_rx_i.ack barred in at least 5 of 6 -> pass. Control v12u r0-r5 reported.
  V5 cpu_control frontend_i.instr barred in 0 of 6 -> pass; 1 of 6 -> no answer; 2 or more -> not. Control v12u r0-r5
     reported.
  V6 cpu r0-r3: no K07/K08 element or OVER[cpu] field barred: 0/4.
  V7 every K01, K02, K04, K05 element barred in both v12v r0-r1; K03 kept (spared) in both; cpu_frontend ctrl_i.if_ack
     barred in at least 5 of 6.
  V8 bus, xbus r0-r1: no K12/K13 element or OVER field barred: 0/4.
  If V1-V8 pass: the round 3 wording becomes the candidate, after a 41-module x 2 run for R1-R4 (not read here).

  python -B p1tighten3.py selftest
  python -B p1tighten3.py preview
  <conda python> p1tighten3.py run v12v    (cap 44)
  <conda python> p1tighten3.py run v12u    (cap 8; separate process: the isolation runner keeps one active variant)
  python -B p1tighten3.py measure          (writes p1tighten3.json)
"""
import json
import sys

import p1tighten2 as P2  # registers v12c_old / v12c_new / v12n / v12t / v12u; shares load(), covered(), CASES

ISO, CH, L, P, RB, AN, run_a = P2.ISO, P2.CH, P2.L, P2.P, P2.RB, P2.AN, P2.run_a
HERE, MODEL, EFFORT, REG, ALU, U = P2.HERE, P2.MODEL, P2.EFFORT, P2.REG, P2.ALU, P2.U
load, covered, CASES = P2.load, P2.covered, P2.CASES
V = json.loads((HERE / "tighten3_P1-23.json").read_text(encoding="utf-8"))["P1-23"]["P1"].replace(P.CRLF, P.LF).strip().split(P.LF)
ISO.VARIANTS["v12v"] = {"run": "rule_isolation_v12v", "texts": str(HERE / "rule_texts_v12v.json"),
                        "ctx": (str(HERE / "context_p1_v10u.md"), str(HERE / "context_p2_v10u.md"))}
CPU, CACHE, LSU, FE, ICC, CTL = "neorv32_cpu", "neorv32_cache", "neorv32_cpu_lsu", "neorv32_cpu_frontend", "neorv32_cpu_icc", "neorv32_cpu_control"
SIXREP = [LSU, FE, ICC, CTL]
FOURREP = [CPU, CACHE]
GUARDS = [REG, ALU, "neorv32_debug_dm", "neorv32_uart", "neorv32_bus", "neorv32_xbus"]
CTRL_MODS = [ICC, CTL]
CAP = {"v12v": 44, "v12u": 8}
OLD_SPAN, NEW_SPAN = "Never a request leaving", "This rule does not cover a request leaving"
PHRASES = ["does not cover", "for storage outside this unit", "nor the command fields it is built from", "nor the response coming back for it",
           "nor a record one instance drives", "nor any field of it"]


def write_texts():
    (HERE / "rule_texts_v12v.json").write_text(json.dumps(
        {"P1-23": {"title": "Access command fields", "P1": P.LF.join(V), "P2": None}}, indent=1, ensure_ascii=False), encoding="utf-8")


def jobs(var):
    ISO.use(var)
    if var == "v12v":
        jl, tx = ISO.jobs(SIXREP, reps=range(6), rules=["P1-23"], phases=("P1",))
        jl += ISO.jobs(FOURREP, reps=range(4), rules=["P1-23"], phases=("P1",))[0]
        jl += ISO.jobs(GUARDS, reps=(0, 1), rules=["P1-23"], phases=("P1",))[0]
    else:
        jl, tx = ISO.jobs(CTRL_MODS, reps=(2, 3, 4, 5), rules=["P1-23"], phases=("P1",))
    return jl, tx, [j for j in jl if not ISO.path(*j).exists()]


def selftest(log=print):
    import check_new_rules as CN
    write_texts()
    checks = {}
    diff = [i for i, (a, b) in enumerate(zip(U, V)) if a != b]
    checks["only 'Never' -> 'This rule does not cover' differs from round 2"] = (
        len(U) == len(V) and len(diff) == 1 and U[diff[0]].count(OLD_SPAN) == 1 and V[diff[0]] == U[diff[0]].replace(OLD_SPAN, NEW_SPAN)
        and "Never" not in P.LF.join(V))
    checks["V block passes check_new_rules"] = not CN.check_text("P1-23", "P1", P.LF.join(V))
    checks["word count 498"] = len(P.LF.join(V).split()) == 498
    ISO.use("v12u")
    tu = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    uu = {m: ISO.user(m, "P1-23", "P1", tu) for m in (REG, LSU, ICC, CTL)}
    su = CH.sha12(ISO.system("P1"))
    stored = {m: json.loads((ISO.run_root(rep=0) / "P1" / "P1-23" / f"{m}.json").read_text(encoding="utf-8"))["user sha"] for m in CTRL_MODS}
    checks["v12u r2-r5 requests (cpu_icc, cpu_control) = its stored r0 requests"] = all(CH.sha12(uu[m]) == stored[m] for m in CTRL_MODS)
    ISO.use("v12v")
    tv = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    uv = {m: ISO.user(m, "P1-23", "P1", tv) for m in (REG, LSU, ICC, CTL)}
    sv = CH.sha12(ISO.system("P1"))
    ISO.use("v9")
    checks["v12v text = V"] = tv["P1-23"]["P1"] == P.LF.join(V)
    checks["v12v and v12u share the clean background"] = sv == su
    checks["v12v request = v12u request with only the span swapped"] = all(uv[m].replace(NEW_SPAN, OLD_SPAN) == uu[m] and uv[m] != uu[m] for m in uv)
    checks["stored v12c_old, v12c_new, v12u r0-r1 complete (82 each)"] = all(
        len(list((P.LAB / "runs" / f"rule_isolation_{s}" / f"{MODEL}__{EFFORT}").glob("r[01]/P1/P1-23/*.json"))) == 82 for s in ("v12c_old", "v12c_new", "v12u"))
    checks["16 cases"] = len(CASES) == 16
    bad = [k for k, v in checks.items() if not v]
    log(f"p1tighten3 self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def cost_of():
    per = {}
    for f in (P.LAB / "runs" / "rule_isolation_v12u" / f"{MODEL}__{EFFORT}").glob("r*/P1/P1-23/*.json"):
        per.setdefault(f.stem, []).append(run_a.usd(json.loads(f.read_text(encoding="utf-8"))["usage"]))
    return {m: sum(v) / len(v) for m, v in per.items()}


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    c = cost_of()
    n = tot = 0
    for var in ("v12v", "v12u"):
        jl, tx, todo = jobs(var)
        est = sum(c[j[2]] for j in todo)
        n += len(todo)
        tot += est
        print(f"{var}: {len(todo)} requests to send (of {len(jl)}), about USD {est:.2f} at v12u's per-module means")
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
    ISO.run(todo, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=44)


def measure():
    groups, refl = RB.CV.groups_and_ref()
    m41 = groups["tuning"] + groups["held-out"]
    old, short = load("v12c_old", m41, (0, 1)), load("v12c_new", m41, (0, 1))
    OVER = {m: (AN.names(short[m][0], "barred") & AN.names(short[m][1], "barred")) - (AN.names(old[m][0], "barred") | AN.names(old[m][1], "barred")) for m in m41}
    v = {**load("v12v", SIXREP, range(6)), **load("v12v", FOURREP, range(4)), **load("v12v", GUARDS, (0, 1))}
    u = load("v12u", CTRL_MODS + [FE, LSU], range(6))
    K = lambda *ids: [e for i in ids for e in CASES[i]["elements"]]
    ids = {CPU: ("K07", "K08"), CACHE: ("K10",), LSU: ("K09",), "neorv32_bus": ("K12",), "neorv32_xbus": ("K13",)}
    replies = [(m, r, x) for m, reps in v.items() for r, x in enumerate(reps)]
    out = {"replies": len(replies), "missing or not parsed": [f"{m[8:]} r{r}" for m, r, x in replies if not isinstance(x, dict)],
           "applies": {m[8:]: [x.get("applies") if isinstance(x, dict) else None for x in reps] for m, reps in v.items()}}
    inv, inv_why = [], []
    for m, r, x in replies:
        for e in (x.get("barred") or []) if isinstance(x, dict) else []:
            rw, why = (e.get("rule words") or ""), (e.get("why") or "")
            if any(p in rw for p in PHRASES):
                inv.append({"module": m[8:], "rep": r, "element": e.get("element"), "rule words": rw[:200]})
            elif any(p in why for p in PHRASES):
                inv_why.append({"module": m[8:], "rep": r, "element": e.get("element"), "why": why[:200]})
    nrep = len({(i["module"], i["rep"]) for i in inv})
    out["V1"] = {"replies with an inverted bar": f"{nrep}/{len(replies)}", "entries": inv, "reported: phrase only in 'why'": inv_why,
                 "reading": "pass" if nrep == 0 else "fail"}

    def cnt(data, m, e):
        return [bool(covered(x, [e])) for x in data[m]]
    fe = cnt(v, FE, "ibus_rsp_i.ack")
    out["V2"] = {"barred per repeat": fe, "barred": f"{sum(fe)}/6", "reading": "pass" if sum(fe) == 0 else "fail"}
    rows = []
    for m in (LSU, CACHE):
        tg = set(K(*ids[m])) | OVER[m]
        rows += [{"module": m[8:], "rep": r, "bars": covered(x, tg)} for r, x in enumerate(v[m])]
    b3 = sum(bool(x["bars"]) for x in rows)
    out["V3"] = {"replies barring": f"{b3}/{len(rows)}", "reading": "out" if b3 == 0 else "no answer" if b3 == 1 else "not",
                 "hits": [x for x in rows if x["bars"]]}
    icc = cnt(v, ICC, "icc_rx_i.ack")
    out["V4"] = {"barred per repeat": icc, "barred": f"{sum(icc)}/6", "reading": "pass" if sum(icc) >= 5 else "fail",
                 "control v12u r0-r5": cnt(u, ICC, "icc_rx_i.ack")}
    ins = cnt(v, CTL, "frontend_i.instr")
    out["V5"] = {"barred per repeat": ins, "barred": f"{sum(ins)}/6", "reading": "pass" if sum(ins) == 0 else "no answer" if sum(ins) == 1 else "not",
                 "control v12u r0-r5": cnt(u, CTL, "frontend_i.instr")}
    tg = set(K("K07", "K08")) | OVER[CPU]
    r6 = [covered(x, tg) for x in v[CPU]]
    out["V6"] = {"bars per repeat": r6, "reading": "pass" if not any(r6) else "fail"}
    v7 = {}
    for cid in ("K01", "K02", "K04", "K05"):
        m = CASES[cid]["module"]
        v7[cid] = {e: sum(bool(covered(x, [e])) for x in v[m]) for e in CASES[cid]["elements"]}
    k3 = {e: sum(isinstance(x, dict) and e in AN.names(x, "spared") for x in v[ALU]) for e in CASES["K03"]["elements"]}
    ifack = cnt(v, FE, "ctrl_i.if_ack")
    out["V7"] = {"repeats barring each element (of 2)": v7, "K03 kept (of 2)": k3, "ctrl_i.if_ack barred per repeat": ifack,
                 "reading": "pass" if all(n == 2 for d in v7.values() for n in d.values()) and all(n == 2 for n in k3.values()) and sum(ifack) >= 5 else "fail"}
    r8 = {m[8:]: [covered(x, set(K(*ids[m])) | OVER[m]) for x in v[m]] for m in ("neorv32_bus", "neorv32_xbus")}
    out["V8"] = {"bars per repeat": r8, "reading": "pass" if not any(b for reps in r8.values() for b in reps) else "fail"}
    out["all pass"] = (out["V1"]["reading"] == "pass" and out["V2"]["reading"] == "pass" and out["V3"]["reading"] == "out"
                       and out["V4"]["reading"] == "pass" and out["V5"]["reading"] == "pass" and out["V6"]["reading"] == "pass"
                       and out["V7"]["reading"] == "pass" and out["V8"]["reading"] == "pass")
    out["reported: blank 'applies: no' replies, v12v"] = sum(isinstance(x, dict) and x.get("applies") == "no" and not (x.get("barred") or x.get("spared") or x.get("unsure")) for _, _, x in replies)
    (HERE / "p1tighten3.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k in ("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"):
        print(k, json.dumps(out[k], ensure_ascii=False)[:700])
    print("applies", json.dumps(out["applies"]))
    print("missing", out["missing or not parsed"], "| blank replies", out["reported: blank 'applies: no' replies, v12v"])
    print("all pass:", out["all pass"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview, "run": lambda: run(sys.argv[2]),
     "measure": measure}[cmd]()
