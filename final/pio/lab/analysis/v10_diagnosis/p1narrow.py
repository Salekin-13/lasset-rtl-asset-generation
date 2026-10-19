"""Re-test of the narrowed Access command fields wording (PLAN_NARROW.md; user 2026-10-17: "Build stage 0 (cells, the v12n
rule-alone variant, self-tests, cost preview), then send all 118 calls in one batch with the readings in PLAN_NARROW.md, and
report."). Diagnostic cells only; the final Phase 1 prompt runs whole.

Wording: NARROW = narrow_P1-23.json (432 words); replaces v10's whole Access command fields block (phase1.md lines 157-168).
Production cells (luna, high, v10's Phase 1 format):
  P1n__C1    K3 (NARROW) + K6 (v10)    cpu_regfile r0-r7
  P1c__C0    K3 + K6, v10 texts        cpu_regfile r4-r7    (drift control; same stored prompt as its r0-r3)
  P1n__C2    K3 (NARROW) + K6 (v10)    cpu_alu r0-r11
  P1c__C2S   K3 (SHORT) + K6 (v10)     cpu_alu r4-r7        (drift control; same stored prompt as its r0-r3)
  P1n__G     K3 (NARROW)               cpu_pmp, cpu_counters, debug_dm, imem r0-r1   (G-old: P1cluster__K3, P1c__Gold)
Rule-alone (isolation format, old reply format, max_tokens 64,000; clean background context_p1_v10u.md): variant v12n
  (NARROW), P1 wording, 41 modules x r0-r1; compared with the stored v12c_old (v10 text) and v12c_new (SHORT).
Readings (copied from PLAN_NARROW.md before sending):
  N1 cpu_regfile: P1n__C1 at most 1/8 broken (3 or more of the 6 barred signals named) -> the control-record condition holds
    with "port"; 3/8 or more -> it does not; 2/8 -> no answer. P1c__C0 r4-r7 at 0/4 -> drift: N1 inconclusive.
  N2 cpu_alu, per reply (broken = names any of the 5 barred signals; pairs reported too): P1n__C2 at most 1/12 -> fixed;
    5/12 or more -> not fixed; 2-4 -> no answer. P1c__C2S r4-r7 at 0/4 -> drift: N2 inconclusive.
  N3 the select's piece: replies where a concept holding line 273 or 318 also holds 274 or 319, or lists a field under
    "Enters Through": at most 1/12 -> the (b) sentence works; 5/12 or more -> it does not. Lines 274/319 in the data concept
    are reported only.
  Guards, per module, for each K3 rule that decides something there: P1n__G not worse than G-old by more than 2 pairs; recall
    guard not below G-old by more than 0.05; every reference signal in both G-old replies and in neither P1n__G reply listed.
  Rule-alone (v12n against v12c_old): R1 hard changes no more than v12c_old's own split signals (29), each listed;
    R2 no reference entry newly barred in both v12n repeats; R3 mean per-module disagreement at most 0.145 + 0.05 and
    contradiction modules at most 2 + 1; R4 cpu_alu fpu_csr_en and cfu_csr_en kept in both repeats, cpu_regfile and cpu_alu
    consistent bars include v10's. Reported, no pass rule: hard changes in bus, cache, cpu, cpu_control, cpu_lsu, xbus
    against v12c_new's 171.
  Adopt NARROW as the Access command fields candidate if N1, R1-R4 and the guards pass; N2/N3 decide whether the (b)
    sentence stays.

  python -B p1narrow.py selftest
  python -B p1narrow.py preview
  <conda python> p1narrow.py run-prod | run-iso       (caps: 36 / 82 new calls)
  python -B p1narrow.py measure                       (writes p1narrow.json)
"""
import json
import re
import sys
import threading

import p1combined as PCB  # registers v12c_old / v12c_new; shares the v10 block, SHORT and the swap

ISO, CH, CK, L, P, PC, PP, RB, AN, run_a = PCB.ISO, PCB.CH, PCB.CK, PCB.L, PCB.P, PCB.PC, PCB.PP, PCB.RB, PCB.AN, PCB.run_a
HERE, MODEL, EFFORT = PCB.HERE, PCB.MODEL, PCB.EFFORT
REG, ALU, GM, REGBARS, OLDBLK = PCB.REG, PCB.ALU, PCB.GM, PCB.REGBARS, PCB.OLDBLK
NARROW = json.loads((HERE / "narrow_P1-23.json").read_text(encoding="utf-8"))["P1-23"]["P1"].replace(P.CRLF, P.LF).strip().split(P.LF)
ISO.VARIANTS["v12n"] = {"run": "rule_isolation_v12n", "texts": str(HERE / "rule_texts_v12n.json"),
                        "ctx": (str(HERE / "context_p1_v10u.md"), str(HERE / "context_p2_v10u.md"))}
OVERREACH = ("bus", "cache", "cpu", "cpu_control", "cpu_lsu", "xbus")
COST = {REG: 0.0133, ALU: 0.0212, "guard": 0.0194, "iso": 0.0099}   # measured means of the D50 batch (PLAN_NARROW.md 6)


def write_texts():
    (HERE / "rule_texts_v12n.json").write_text(json.dumps(
        {"P1-23": {"title": "Access command fields", "P1": P.LF.join(NARROW), "P2": None}}, indent=1, ensure_ascii=False), encoding="utf-8")


def cells():
    K = PP.clusters()
    k3k6 = K["K3"] + K["K6"]
    return {
        "P1n__C1": (k3k6, NARROW, [REG], range(8)),
        "P1c__C0": (k3k6, None, [REG], range(4, 8)),
        "P1n__C2": (k3k6, NARROW, [ALU], range(12)),
        "P1c__C2S": (k3k6, PCB.SHORT, [ALU], range(4, 8)),
        "P1n__G": (K["K3"], NARROW, GM, range(2)),
    }


def text_of(name):
    keep, blk, _, _ = cells()[name]
    base = P.build_keep(keep)
    return PCB.swap(base, blk) if blk else base


def selftest(log=print):
    import check_new_rules as CN
    write_texts()
    checks = {}
    for name, (keep, blk, mods, reps) in cells().items():
        base = P.build_keep(keep).split(P.LF)
        t = text_of(name).split(P.LF)
        if blk:
            i = [k for k in range(len(base)) if base[k:k + len(OLDBLK)] == OLDBLK][0]
            checks[f"{name}: only the Access command fields block differs"] = t[:i] == base[:i] and t[i + len(blk):] == base[i + len(OLDBLK):] and t[i:i + len(blk)] == blk
        active = {P.base_title(x) for _, _, x in P.blocks(t, t.index("OUTPUT"))}
        checks[f"{name}: active rules as planned"] = active == set(keep)
        log(f"{name}: {len(P.LF.join(t).split())} words; {[m[8:] for m in mods]} x r{min(reps)}-r{max(reps)}")
    # the two drift controls continue stored cells: same prompt on disk, stored r0-r3 carry today's system sha
    for name, mod in (("P1c__C0", REG), ("P1c__C2S", ALU)):
        disk = (P.LAB / "prompts" / "diag_v10" / name / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF)
        sha = CH.sha12(CK.system(f"diag_v10/{name}", 1))
        stored = {json.loads((L.cell_dir(name, r) / "phase1" / f"{mod}.json").read_text(encoding="utf-8"))["system sha"] for r in range(4)}
        checks[f"{name}: prompt on disk = builder = p1combined's, stored r0-r3 sha = today's"] = (
            disk == text_of(name) == PCB.text_of(name) and stored == {sha})
    for m in GM:
        old = "P1c__Gold" if m == "neorv32_cpu_counters" else "P1cluster__K3"
        checks[f"G-old {old} has {m[8:]} r0-r1"] = all((L.cell_dir(old, r) / "phase1" / f"{m}.json").exists() for r in (0, 1))
    checks["NARROW block passes check_new_rules"] = not CN.check_text("P1-23", "P1", P.LF.join(NARROW))
    checks["word counts v10 313 / short 407 / narrow 432"] = [len(P.LF.join(b).split()) for b in (OLDBLK, PCB.SHORT, NARROW)] == [313, 407, 432]
    for s in ("Scope: Accesses on a record port, a processor's control record port included",
              "an instance's included where this unit's statements decode or gate the access to it",
              "never an access it only passes on through an output port.",
              "that signal alone", "no field or write enable (a) bars joins it, even one it gates."):
        checks[f"NARROW carries {s[:40]!r}"] = P.LF.join(NARROW).count(s) == 1
    checks["NARROW drops the held-line fix"] = "the written data's included" not in P.LF.join(NARROW)
    # rule-alone: v12n differs from v12c_old only in the rule text; same clean background
    ISO.use("v12c_old")
    to = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    uo = {m: ISO.user(m, "P1-23", "P1", to) for m in (REG, ALU)}
    so = CH.sha12(ISO.system("P1"))
    ISO.use("v12n")
    tn = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    un = {m: ISO.user(m, "P1-23", "P1", tn) for m in (REG, ALU)}
    sn = CH.sha12(ISO.system("P1"))
    ISO.use("v9")
    checks["rule-alone v12n text = NARROW"] = tn["P1-23"]["P1"] == P.LF.join(NARROW)
    checks["rule-alone v12n and v12c_old share the clean background"] = so == sn
    checks["rule-alone v12n request = v12c_old request with only the rule text swapped"] = all(
        un[m].replace(P.LF.join(NARROW), P.LF.join(OLDBLK)) == uo[m] and un[m] != uo[m] for m in (REG, ALU))
    checks["v12c_old and v12c_new stored replies complete (41 x 2 each)"] = all(
        len(list((P.LAB / "runs" / f"rule_isolation_v12c_{s}" / f"{MODEL}__{EFFORT}").glob("r*/P1/P1-23/*.json"))) == 82 for s in ("old", "new"))
    bad = [k for k, v in checks.items() if not v]
    log(f"p1narrow self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def prod_jobs():
    jobs = []
    for rep in range(12):
        for name, (keep, blk, mods, reps) in cells().items():
            if rep in reps:
                for m in mods:
                    if not (L.cell_dir(name, rep) / "phase1" / f"{m}.json").exists():
                        jobs.append((name, rep, m))
    return jobs


def iso_jobs():
    ISO.use("v12n")
    jl, tx = ISO.jobs(None, reps=(0, 1), rules=["P1-23"], phases=("P1",))
    todo = [j for j in jl if not ISO.path(*j).exists()]
    return jl, tx, todo


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    pj = prod_jobs()
    est = sum(COST["guard"] if name == "P1n__G" else COST[m] for name, _, m in pj)
    print(f"production: {len(pj)} calls, about USD {est:.2f} (D50 measured means)")
    jl, tx, todo = iso_jobs()
    ISO.preview(jl, tx)
    ISO.use("v9")
    print(f"rule-alone: {len(todo)} requests, about USD {len(todo) * COST['iso']:.2f} (v12c_new's measured mean)")
    print(f"total new calls: {len(pj) + len(todo)}, about USD {est + len(todo) * COST['iso']:.2f}; "
          f"spent so far USD {run_a.spent(log=lambda *a: None):.2f}")


def run_prod():
    from concurrent.futures import ThreadPoolExecutor
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    vers = {n: P.cell_version(n, text_of(n)) for n in cells()}
    L.track_folders(list(cells()))
    jobs, calls, stop = prod_jobs(), {}, CH._new_run_flag()
    if len(jobs) > 36:
        sys.exit("more than 36 production calls; nothing sent")
    for name, rep, m in jobs:
        if (name, rep) not in calls:
            out = L.cell_dir(name, rep)
            out.mkdir(parents=True, exist_ok=True)
            calls[(name, rep)] = CH.openai(MODEL, EFFORT, out=out, poll=5)

    def one(j):
        threading.current_thread().lab_stop = stop
        name, rep, m = j
        out = L.cell_dir(name, rep)
        return CH._ask(calls[(name, rep)], CK.system(vers[name], 1), CH.user_message(vers[name], 1, m), out / "phase1" / f"{m}.json",
                       lambda o: CH.check_phase1(m, o), {"module": m, "prompt version": vers[name], "phase": 1},
                       adapt=CH.from_format_phase1).get("problems")
    print(f"production: sending {len(jobs)}")
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        res = list(pool.map(one, jobs))
    print("production done", len(res), "; problems", [r for r in res if r])


def run_iso():
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    jl, tx, todo = iso_jobs()
    if len(todo) > 82:
        sys.exit("more than 82 rule-alone requests; nothing sent")
    for r in (0, 1):
        ISO.run_root(rep=r).mkdir(parents=True, exist_ok=True)
    tracked = [str(P.LAB / "runs" / "rule_isolation_v12n" / f"{MODEL}__{EFFORT}")]
    ex = json.loads(L.EXTRA.read_text(encoding="utf-8")) if L.EXTRA.exists() else []
    L.EXTRA.write_text(json.dumps(ex + [p for p in tracked if p not in ex], indent=1), encoding="utf-8")
    print(f"rule-alone v12n: sending {len(todo)}")
    ISO.run(jl, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=41)


def rec_of(cell, rep, m):
    return json.loads((L.cell_dir(cell, rep) / "phase1" / f"{m}.json").read_text(encoding="utf-8"))


def alu_row(rec, abars):
    named = [e for e in abars if P.p1_named(rec, ALU, e) == "named"]
    cs = rec["reply"]["conceptual assets"]
    held = [set(c.get("held lines") or []) for c in cs]
    sel = [i for i, h in enumerate(held) if h & {273, 318}]
    fields = {e for e in abars if e.startswith("ctrl_i.")}
    n3 = any(held[i] & {274, 319} or fields & set(cs[i].get("enters through") or []) for i in sel)
    other274 = any(h & {274, 319} for i, h in enumerate(held) if i not in sel)
    return {"named": named, "broken": bool(named), "N3 select piece": n3, "274/319 held outside a 273/318 concept": other274,
            "concepts": [c.get("concept") for c in cs if set(c.get("held lines") or []) & {273, 274, 318, 319}
                         or fields & set(c.get("enters through") or [])]}


def measure():
    out = {}
    for name, reps in (("P1c__C0", range(4, 8)), ("P1n__C1", range(8))):
        rows = []
        for r in reps:
            rec = rec_of(name, r, REG)
            k = sum(P.p1_named(rec, REG, e) == "named" for e in REGBARS)
            rows.append({"rep": r, "named": k, "broken": k >= 3, "concepts": len(rec["reply"]["conceptual assets"])})
        out[name] = {"broken": f"{sum(x['broken'] for x in rows)}/{len(rows)}", "rows": rows}
    c0 = int(out["P1c__C0"]["broken"].split("/")[0])
    b1 = int(out["P1n__C1"]["broken"].split("/")[0])
    out["N1"] = "inconclusive (drift: C0 r4-r7 0/4)" if c0 == 0 else "holds" if b1 <= 1 else "does not hold" if b1 >= 3 else "no answer"
    abars = sorted(L.bars("P1-23 P2", [ALU])[ALU])
    out["cpu_alu barred signals"] = abars
    for name, reps in (("P1c__C2S", range(8)), ("P1n__C2", range(12))):
        rows = [{"rep": r, **alu_row(rec_of(name, r, ALU), abars)} for r in reps]
        out[name] = {"replies broken": f"{sum(x['broken'] for x in rows)}/{len(rows)}",
                     "pairs named": f"{sum(len(x['named']) for x in rows)}/{5 * len(rows)}",
                     "N3 select piece": f"{sum(x['N3 select piece'] for x in rows)}/{len(rows)}",
                     "274/319 held outside a 273/318 concept": f"{sum(x['274/319 held outside a 273/318 concept'] for x in rows)}/{len(rows)}",
                     "rows": rows}
    drift = [x for x in out["P1c__C2S"]["rows"] if x["rep"] >= 4]
    d2 = sum(x["broken"] for x in drift)
    out["P1c__C2S"]["r4-r7 broken"] = f"{d2}/4"
    b2 = int(out["P1n__C2"]["replies broken"].split("/")[0])
    n3 = int(out["P1n__C2"]["N3 select piece"].split("/")[0])
    out["N2"] = "inconclusive (drift: C2S r4-r7 0/4)" if d2 == 0 else "fixed" if b2 <= 1 else "not fixed" if b2 >= 5 else "no answer"
    out["N3"] = "works" if n3 <= 1 else "does not work" if n3 >= 5 else "no answer"
    groups, refl = RB.CV.groups_and_ref()
    mods41 = groups["tuning"] + groups["held-out"]
    dec = PC.decisions(mods41)
    T = PC.titles()
    K3 = [r for r in dec if T.get(r) in PP.clusters()["K3"]]
    guards = {}
    for m in GM:
        old = "P1c__Gold" if m == "neorv32_cpu_counters" else "P1cluster__K3"
        recs = {s: [rec_of(c, r, m) for r in (0, 1)] for s, c in (("new", "P1n__G"), ("old", old), ("short", "P1c__Gshort"))}
        g = {}
        for rid in K3:
            els = sorted(dec[rid].get(m, ()))
            if not els:
                continue
            keep = rid in PC.KEEP
            sc = {s: sum(PC.score(x, m, els, keep)[0] for x in recs[s]) for s in recs}
            g[T[rid]] = {"followed narrow": sc["new"], "followed old": sc["old"], "followed short": sc["short"],
                         "pairs": 2 * len(els), "flag": sc["new"] < sc["old"] - 2}
        ref = sorted(refl.get(m, ()))
        st = {s: [[P.p1_named(x, m, e) for e in ref] for x in recs[s]] for s in recs}
        gn = {s: sum(v != "not in Phase 1" for row in st[s] for v in row) / (2 * len(ref)) if ref else None for s in st}
        lost = [e for i, e in enumerate(ref) if all(st["old"][r][i] != "not in Phase 1" for r in (0, 1)) and all(st["new"][r][i] == "not in Phase 1" for r in (0, 1))]
        guards[m[8:]] = {"rules": g, "recall guard narrow / old / short": [round(gn[s], 2) for s in ("new", "old", "short")] if ref else None,
                         "guard flag": bool(ref) and gn["new"] < gn["old"] - 0.05, "reference lost": lost}
    out["guards"] = guards
    out["guards pass"] = not any(v["guard flag"] or v["reference lost"] or any(x["flag"] for x in v["rules"].values()) for v in guards.values())
    # rule-alone
    import read_v11n as RV
    side = {}
    for s, var in (("old", "v12c_old"), ("short", "v12c_new"), ("narrow", "v12n")):
        ISO.use(var)
        side[s] = {m: [json.loads((ISO.run_root(rep=r) / "P1" / "P1-23" / f"{m}.json").read_text(encoding="utf-8")).get("reply")
                       if (ISO.run_root(rep=r) / "P1" / "P1-23" / f"{m}.json").exists() else None for r in (0, 1)] for m in mods41}
    ISO.use("v9")

    def compare(a, b):
        hard, split_a, newbar_ref, dis, contra, missing = [], 0, [], {a: [], b: []}, {a: 0, b: 0}, []
        for m in mods41:
            o, n = side[a][m], side[b][m]
            if None in o or None in n or not all(isinstance(x, dict) for x in o + n):
                missing.append(m[8:])
                continue
            for key in ("barred", "spared"):
                O = [AN.names(x, key) for x in o]
                N = [AN.names(x, key) for x in n]
                split_a += len(O[0] ^ O[1])
                for e in sorted((O[0] & O[1]) - (N[0] | N[1])):
                    hard.append({"module": m[8:], "signal": e, "change": f"{key} both {a}, neither {b}"})
                for e in sorted((N[0] & N[1]) - (O[0] | O[1])):
                    hard.append({"module": m[8:], "signal": e, "change": f"{key} both {b}, neither {a}"})
            for e in refl.get(m, ()):
                if all(RB.down(e, AN.names(x, "barred")) for x in n) and not all(RB.down(e, AN.names(x, "barred")) for x in o):
                    newbar_ref.append(f"{m[8:]}: {e}")
            for s, reps in ((a, o), (b, n)):
                d, c, _, _ = RV.decide(reps, keep=False)
                if d is not None:
                    dis[s].append(d)
                contra[s] += c
        md = {s: round(sum(v) / len(v), 3) if v else 0.0 for s, v in dis.items()}
        return hard, split_a, newbar_ref, md, contra, missing

    hard, split_old, newbar_ref, md, contra, missing = compare("old", "narrow")
    hard_s = compare("old", "short")[0]
    nalu = side["narrow"][ALU]
    keeps = all(isinstance(x, dict) and {"fpu_csr_en", "cfu_csr_en"} <= AN.names(x, "spared") for x in nalu)
    incl = {}
    for m in (REG, ALU):
        ob = AN.names(side["old"][m][0], "barred") & AN.names(side["old"][m][1], "barred")
        nb = AN.names(side["narrow"][m][0], "barred") & AN.names(side["narrow"][m][1], "barred")
        incl[m[8:]] = {"old consistent bars": sorted(ob), "narrow consistent bars": sorted(nb), "narrow includes old": ob <= nb}
    from collections import Counter
    by_mod = Counter(h["module"] for h in hard)
    by_mod_s = Counter(h["module"] for h in hard_s)
    out["rule-alone"] = {
        "replies missing or not parsed": missing,
        "R1 hard changes": len(hard), "R1 floor (old split signals)": split_old, "R1 pass": len(hard) <= split_old,
        "hard changes by module, narrow / short": {k: [by_mod.get(k, 0), by_mod_s.get(k, 0)] for k in sorted(set(by_mod) | set(by_mod_s))},
        "over-reach modules narrow / short": [sum(by_mod.get(k, 0) for k in OVERREACH), sum(by_mod_s.get(k, 0) for k in OVERREACH)],
        "R2 reference newly barred in both narrow repeats": newbar_ref, "R2 pass": not newbar_ref,
        "R3 mean disagreement old / narrow": [md["old"], md["narrow"]], "R3 contradiction modules old / narrow": [contra["old"], contra["narrow"]],
        "R3 pass": md["narrow"] <= md["old"] + 0.05 and contra["narrow"] <= contra["old"] + 1,
        "R4 cpu_alu selects kept in both narrow repeats": keeps, "R4 consistent bars": incl,
        "R4 pass": keeps and all(v["narrow includes old"] for v in incl.values()),
        "hard changes": hard}
    ra = out["rule-alone"]
    out["adopt narrow as the candidate"] = (out["N1"] == "holds" and ra["R1 pass"] and ra["R2 pass"] and ra["R3 pass"]
                                            and ra["R4 pass"] and out["guards pass"])
    (HERE / "p1narrow.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    brief = {k: v for k, v in out.items() if k not in ("guards", "rule-alone")}
    for k in ("P1c__C2S", "P1n__C2"):
        brief[k] = {x: y for x, y in out[k].items() if x != "rows"}
    print(json.dumps(brief, indent=1, ensure_ascii=False)[:5000])
    print(json.dumps(out["guards"], indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in ra.items() if k != "hard changes"}, indent=1, ensure_ascii=False))
    for h in ra["hard changes"]:
        print(f"  {h['module']}: {h['signal']} ({h['change']})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview, "run-prod": run_prod,
     "run-iso": run_iso, "measure": measure}[cmd]()
