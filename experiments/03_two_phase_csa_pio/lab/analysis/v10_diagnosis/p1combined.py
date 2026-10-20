"""Combined test of the new Access command fields wording (PLAN_COMBINED.md; user 2026-10-17: "Build stage 0 (all cells and
the rule-alone variants, self-tests, cost preview), then send all 202 calls in one batch with the readings in
PLAN_COMBINED.md, and report."). Diagnostic cells only; the final Phase 1 prompt runs whole.

Wordings: LONG = combined_P1-23.json (470 words), SHORT = short_P1-23.json (407 words); each replaces v10's whole Access
command fields block (phase1.md lines 157-168, 313 words).
Production cells (luna, high, v10's Phase 1 format):
  P1c__C0      K3 + K6, v10 texts           cpu_regfile r0-r3   (drift control; = stored P1pair__K3_K6 prompt)
  P1c__C1L/S   K3 (LONG/SHORT) + K6 (v10)   cpu_regfile r0-r7
  P1c__C2L/S   K3 (LONG/SHORT) + K6 (v10)   cpu_alu r0-r3
  P1c__Gshort  K3 (SHORT)                   cpu_pmp, cpu_counters, debug_dm, imem r0-r1
  P1c__Gold    K3 (v10)                     cpu_counters r0-r1 (cpu_pmp, debug_dm, imem: stored P1cluster__K3, same prompt)
Rule-alone (isolation format, old reply format, max_tokens 64,000; clean background context_p1_v10u.md = v10's Phase 1 core
  with no other rule): variants v12c_old (v10 text) and v12c_new (SHORT), P1 wording, 41 modules x r0-r1.
Readings (copied from PLAN_COMBINED.md before sending):
  C1L, C1S each: at most 1/8 broken (3 or more of the 6 barred signals named) -> the scope condition holds; 3/8 or more ->
    it does not; 2/8 -> no answer. C0: 0/4 broken -> drift: C1L and C1S inconclusive.
  C2L, C2S each, naming: named pairs out of 20 (5 barred signals): at most 2 -> holds; 6 or more -> not; 3-5 -> no answer.
  C2L, C2S each, held lines: replies citing line 274 or 319 as a held line of any concept: at most 1/4 -> the held-line fix
    works; 3/4 or more -> it does not; 2/4 -> no answer.
  Guards, per module, for each K3 rule that decides something there (p1clusters.score: bar rules = pairs not named; keep
    rules = pairs named or held): G-new not worse than G-old by more than 2 pairs; recall guard (reference signals Phase 1
    names or line-links) not below G-old by more than 0.05; every reference signal present in both G-old replies and
    absent from both G-new replies is listed.
  Shortening verdict: adopt SHORT if C1S, C2S (naming and held lines) and the guards pass. If LONG passes a reading SHORT
    fails, the shortening lost that condition.
  Rule-alone: hard changes (signals one side decides the same way in both repeats, bars or keeps, that the other side
    decides in neither repeat) no more than OLD's own split signals (decided in exactly one OLD repeat), each listed; no
    reference entry newly barred in both NEW repeats; NEW mean per-module disagreement at most OLD + 0.05 and contradiction
    modules at most OLD + 1; cpu_alu fpu_csr_en and cfu_csr_en kept in both NEW repeats; cpu_regfile and cpu_alu NEW
    consistent bars include OLD's.

  python -B p1combined.py selftest
  python -B p1combined.py preview
  <conda python> p1combined.py run-prod | run-iso old | run-iso new     (caps: 38 / 82 / 82 new calls)
  python -B p1combined.py measure     (writes p1combined.json)
"""
import json
import os
import re
import sys
import threading
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import check_lab_prompt as CK  # noqa: E402
import ladder as L  # noqa: E402
import p1probe as P  # noqa: E402
import p1clusters as PC  # noqa: E402
import p1pairs as PP  # noqa: E402
import rule_breaks as RB  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import run_a  # noqa: E402

V10P1 = P.V10D.joinpath("phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF).split(P.LF)
OLDBLK = V10P1[156:168]
LONG = json.loads((HERE / "combined_P1-23.json").read_text(encoding="utf-8"))["P1-23"]["P1"].replace(P.CRLF, P.LF).strip().split(P.LF)
SHORT = json.loads((HERE / "short_P1-23.json").read_text(encoding="utf-8"))["P1-23"]["P1"].replace(P.CRLF, P.LF).strip().split(P.LF)
REG, ALU = "neorv32_cpu_regfile", "neorv32_cpu_alu"
GM = ["neorv32_cpu_pmp", "neorv32_cpu_counters", "neorv32_debug_dm", "neorv32_imem"]
REGBARS = ["ctrl_i.rf_rd", "ctrl_i.rf_rs1", "ctrl_i.rf_rs2", "ctrl_i.rf_wb_en", "ctrl_i.rf_zero_we", "rf_we"]
ISO.VARIANTS["v12c_old"] = {"run": "rule_isolation_v12c_old", "texts": str(HERE / "rule_texts_v12c_old.json"),
                            "ctx": (str(HERE / "context_p1_v10u.md"), str(HERE / "context_p2_v10u.md"))}
ISO.VARIANTS["v12c_new"] = {"run": "rule_isolation_v12c_new", "texts": str(HERE / "rule_texts_v12c_new.json"),
                            "ctx": (str(HERE / "context_p1_v10u.md"), str(HERE / "context_p2_v10u.md"))}


def write_texts():
    for v, blk in (("old", OLDBLK), ("new", SHORT)):
        (HERE / f"rule_texts_v12c_{v}.json").write_text(json.dumps(
            {"P1-23": {"title": "Access command fields", "P1": P.LF.join(blk), "P2": None}}, indent=1, ensure_ascii=False), encoding="utf-8")


def swap(text, blk):
    t = text.split(P.LF)
    i = [k for k in range(len(t)) if t[k:k + len(OLDBLK)] == OLDBLK]
    assert len(i) == 1, "v10 block not found once"
    return P.LF.join(t[:i[0]] + blk + t[i[0] + len(OLDBLK):])


def cells():
    K = PP.clusters()
    k3k6 = K["K3"] + K["K6"]
    return {
        "P1c__C0": (k3k6, None, [REG], range(4)),
        "P1c__C1L": (k3k6, LONG, [REG], range(8)), "P1c__C1S": (k3k6, SHORT, [REG], range(8)),
        "P1c__C2L": (k3k6, LONG, [ALU], range(4)), "P1c__C2S": (k3k6, SHORT, [ALU], range(4)),
        "P1c__Gshort": (K["K3"], SHORT, GM, range(2)),
        "P1c__Gold": (K["K3"], None, ["neorv32_cpu_counters"], range(2)),
    }


def text_of(name):
    keep, blk, _, _ = cells()[name]
    base = P.build_keep(keep)
    return swap(base, blk) if blk else base


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
        log(f"{name}: {len(P.LF.join(t).split())} words; {[m[8:] for m in mods]} x {len(list(reps))}")
    for name, stored in (("P1c__C0", "P1pair__K3_K6"), ("P1c__Gold", "P1cluster__K3")):
        s = (P.LAB / "prompts" / "diag_v10" / stored / "phase1.md").read_text(encoding="utf-8").replace(P.CRLF, P.LF)
        checks[f"{name} = stored {stored} prompt"] = text_of(name) == s
    for m in GM[:1] + GM[2:]:
        checks[f"G-old stored P1cluster__K3 {m[8:]} r0-r1"] = all((L.cell_dir("P1cluster__K3", r) / "phase1" / f"{m}.json").exists() for r in (0, 1))
    checks["LONG block passes check_new_rules"] = not CN.check_text("P1-23", "P1", P.LF.join(LONG))
    checks["SHORT block passes check_new_rules"] = not CN.check_text("P1-23", "P1", P.LF.join(SHORT))
    checks["word counts 313 / 470 / 407"] = [len(P.LF.join(b).split()) for b in (OLDBLK, LONG, SHORT)] == [313, 470, 407]
    # rule-alone: OLD's text is the tested v10 text (same user message as the stored v10r request); NEW differs only in the rule
    ISO.use("v12c_old")
    to = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    uo = CH.sha12(ISO.user(REG, "P1-23", "P1", to))
    so = CH.sha12(ISO.system("P1"))
    ISO.use("v10r")
    stored_u = json.loads((ISO.run_root(rep=0) / "P1" / "P1-23" / f"{REG}.json").read_text(encoding="utf-8"))["user sha"]
    stored_s = json.loads((ISO.run_root(rep=0) / "P1" / "P1-23" / f"{REG}.json").read_text(encoding="utf-8"))["system sha"]
    ISO.use("v12c_new")
    tn = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    sn = CH.sha12(ISO.system("P1"))
    ISO.use("v9")
    checks["rule-alone OLD user message = the stored v10r P1-23 request (same rule text)"] = uo == stored_u
    checks["rule-alone OLD background differs from the stored one (clean context)"] = so != stored_s
    checks["rule-alone OLD and NEW share the clean background"] = so == sn
    checks["rule-alone NEW text = SHORT"] = tn["P1-23"]["P1"] == P.LF.join(SHORT)
    ctx = (HERE / "context_p1_v10u.md").read_text(encoding="utf-8")
    checks["clean background holds no rule block"] = not any(l.startswith("- " + t + " ") or l.startswith("- " + t + ".") for t in P.order() for l in ctx.split("\n"))
    bad = [k for k, v in checks.items() if not v]
    log(f"p1combined self-test ({len(checks)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def prod_jobs():
    jobs = []
    for rep in range(8):
        for name, (keep, blk, mods, reps) in cells().items():
            if rep in reps:
                for m in mods:
                    if not (L.cell_dir(name, rep) / "phase1" / f"{m}.json").exists():
                        jobs.append((name, rep, m))
    return jobs


def iso_jobs(side):
    ISO.use(f"v12c_{side}")
    jl, tx = ISO.jobs(None, reps=(0, 1), rules=["P1-23"], phases=("P1",))
    todo = [j for j in jl if not ISO.path(*j).exists()]
    return jl, tx, todo


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    pj = prod_jobs()
    print(f"production: {len(pj)} calls, about USD {len(pj) * 0.017:.2f}-{len(pj) * 0.022:.2f} (measured means of the last two batches)")
    tot = 0
    for side in ("old", "new"):
        jl, tx, todo = iso_jobs(side)
        ISO.preview(jl, tx)
        tot += len(todo)
        ISO.use("v9")
    print(f"rule-alone: {tot} requests, about USD {tot * 0.0077:.2f} at this rule's measured mean (USD 0.0077 per request)")
    print(f"total new calls: {len(pj) + tot}; spent so far USD {run_a.spent(log=lambda *a: None):.2f}")


def run_prod():
    from concurrent.futures import ThreadPoolExecutor
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    vers = {n: P.cell_version(n, text_of(n)) for n in cells()}
    L.track_folders(list(cells()))
    jobs, calls, stop = prod_jobs(), {}, CH._new_run_flag()
    if len(jobs) > 38:
        sys.exit("more than 38 production calls; nothing sent")
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


def run_iso(side):
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    jl, tx, todo = iso_jobs(side)
    if len(todo) > 82:
        sys.exit("more than 82 rule-alone requests; nothing sent")
    for r in (0, 1):
        ISO.run_root(rep=r).mkdir(parents=True, exist_ok=True)
    tracked = [str(P.LAB / "runs" / f"rule_isolation_v12c_{side}" / f"{MODEL}__{EFFORT}")]
    ex = json.loads(L.EXTRA.read_text(encoding="utf-8")) if L.EXTRA.exists() else []
    L.EXTRA.write_text(json.dumps(ex + [p for p in tracked if p not in ex], indent=1), encoding="utf-8")
    print(f"rule-alone {side}: sending {len(todo)}")
    ISO.run(jl, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=41)


def measure():
    out = {}
    nk = re.compile(r"access[- ]command|command[- ]field", re.I)
    for name in ("P1c__C0", "P1c__C1L", "P1c__C1S"):
        n = len(list(cells()[name][3]))
        rows = []
        for r in range(n):
            rec = json.loads((L.cell_dir(name, r) / "phase1" / f"{REG}.json").read_text(encoding="utf-8"))
            k = sum(P.p1_named(rec, REG, e) == "named" for e in REGBARS)
            rows.append({"named": k, "broken": k >= 3, "Not Kept access": bool(nk.search(json.dumps(rec["reply"].get("considered, not kept") or []))),
                         "concepts": len(rec["reply"]["conceptual assets"])})
        b = sum(x["broken"] for x in rows)
        out[name] = {"broken": f"{b}/{n}", "rows": rows}
        print(f"{name}: broken {b}/{n} named {[x['named'] for x in rows]} NotKept-access {[int(x['Not Kept access']) for x in rows]}")
    c0 = int(out["P1c__C0"]["broken"].split("/")[0])
    for name in ("P1c__C1L", "P1c__C1S"):
        b = int(out[name]["broken"].split("/")[0])
        out[name]["reading"] = "inconclusive (drift: C0 0/4)" if c0 == 0 else "holds" if b <= 1 else "does not hold" if b >= 3 else "no answer"
    abars = sorted(L.bars("P1-23 P2", [ALU])[ALU])
    for name in ("P1c__C2L", "P1c__C2S"):
        named = held = 0
        rows = []
        for r in range(4):
            rec = json.loads((L.cell_dir(name, r) / "phase1" / f"{ALU}.json").read_text(encoding="utf-8"))
            k = sum(P.p1_named(rec, ALU, e) == "named" for e in abars)
            h = any({274, 319} & set(c.get("held lines") or []) for c in rec["reply"]["conceptual assets"])
            named += k
            held += h
            rows.append({"named": k, "holds 274/319": h})
        out[name] = {"named": f"{named}/20", "naming": "holds" if named <= 2 else "not" if named >= 6 else "no answer",
                     "holds 274/319": f"{held}/4", "held-line fix": "works" if held <= 1 else "does not" if held >= 3 else "no answer", "rows": rows}
        print(f"{name}: named {named}/20 -> {out[name]['naming']}; holds 274/319 {held}/4 -> {out[name]['held-line fix']}")
    groups, refl = RB.CV.groups_and_ref()
    mods41 = groups["tuning"] + groups["held-out"]
    dec = PC.decisions(mods41)
    T = PC.titles()
    K3 = [r for r in dec if T.get(r) in PP.clusters()["K3"]]
    guards = {}
    for m in GM:
        old = "P1c__Gold" if m == "neorv32_cpu_counters" else "P1cluster__K3"
        recs = {s: [json.loads((L.cell_dir(c, r) / "phase1" / f"{m}.json").read_text(encoding="utf-8")) for r in (0, 1)]
                for s, c in (("new", "P1c__Gshort"), ("old", old))}
        g = {}
        for rid in K3:
            els = sorted(dec[rid].get(m, ()))
            if not els:
                continue
            keep = rid in PC.KEEP
            sc = {s: sum(PC.score(x, m, els, keep)[0] for x in recs[s]) for s in recs}
            g[T[rid]] = {"followed new": sc["new"], "followed old": sc["old"], "pairs": 2 * len(els), "flag": sc["new"] < sc["old"] - 2}
        ref = sorted(refl.get(m, ()))
        st = {s: [[P.p1_named(x, m, e) for e in ref] for x in recs[s]] for s in recs}
        gn = {s: sum(v != "not in Phase 1" for row in st[s] for v in row) / (2 * len(ref)) if ref else None for s in st}
        lost = [e for i, e in enumerate(ref) if all(st["old"][r][i] != "not in Phase 1" for r in (0, 1)) and all(st["new"][r][i] == "not in Phase 1" for r in (0, 1))]
        guards[m[8:]] = {"rules": g, "recall guard new / old": [round(gn["new"], 2), round(gn["old"], 2)] if ref else None,
                         "guard flag": bool(ref) and gn["new"] < gn["old"] - 0.05, "reference lost": lost}
        print(f"guard {m[8:]}: {g} | recall guard new/old {guards[m[8:]]['recall guard new / old']} | lost {lost}")
    out["guards"] = guards
    out["guards pass"] = not any(v["guard flag"] or v["reference lost"] or any(x["flag"] for x in v["rules"].values()) for v in guards.values())
    # rule-alone
    import read_v11n as RV
    side = {}
    for s in ("old", "new"):
        ISO.use(f"v12c_{s}")
        side[s] = {m: [json.loads((ISO.run_root(rep=r) / "P1" / "P1-23" / f"{m}.json").read_text(encoding="utf-8")).get("reply")
                       if (ISO.run_root(rep=r) / "P1" / "P1-23" / f"{m}.json").exists() else None for r in (0, 1)] for m in mods41}
    ISO.use("v9")
    hard, split_old, newbar_ref, dis, contra = [], 0, [], {"old": [], "new": []}, {"old": 0, "new": 0}
    for m in mods41:
        o, n = side["old"][m], side["new"][m]
        if None in o or None in n or not all(isinstance(x, dict) for x in o + n):
            continue
        for key in ("barred", "spared"):
            O = [AN.names(x, key) for x in o]
            N = [AN.names(x, key) for x in n]
            split_old += len(O[0] ^ O[1])
            for e in (O[0] & O[1]) - (N[0] | N[1]):
                hard.append(f"{m[8:]}: {e} ({key} both OLD, neither NEW)")
            for e in (N[0] & N[1]) - (O[0] | O[1]):
                hard.append(f"{m[8:]}: {e} ({key} both NEW, neither OLD)")
        for e in refl.get(m, ()):
            if all(RB.down(e, AN.names(x, "barred")) for x in n) and not all(RB.down(e, AN.names(x, "barred")) for x in o):
                newbar_ref.append(f"{m[8:]}: {e}")
        for s, reps in (("old", o), ("new", n)):
            d, c, _, _ = RV.decide(reps, keep=False)
            if d is not None:
                dis[s].append(d)
            contra[s] += c
    md = {s: round(sum(v) / len(v), 3) if v else 0.0 for s, v in dis.items()}
    nalu = side["new"][ALU]
    keeps = all(isinstance(x, dict) and {"fpu_csr_en", "cfu_csr_en"} <= AN.names(x, "spared") for x in nalu)
    incl = {}
    for m in (REG, ALU):
        ob = AN.names(side["old"][m][0], "barred") & AN.names(side["old"][m][1], "barred")
        nb = AN.names(side["new"][m][0], "barred") & AN.names(side["new"][m][1], "barred")
        incl[m[8:]] = {"old consistent bars": sorted(ob), "new consistent bars": sorted(nb), "new includes old": ob <= nb}
    out["rule-alone"] = {"hard changes": hard, "OLD split signals": split_old, "hard changes pass": len(hard) <= split_old,
                         "reference newly barred in both NEW repeats": newbar_ref, "mean disagreement old / new": md,
                         "contradiction modules old / new": contra, "clarity pass": md["new"] <= md["old"] + 0.05 and contra["new"] <= contra["old"] + 1,
                         "cpu_alu selects kept in both NEW repeats": keeps, "consistent bars": incl}
    print(json.dumps(out["rule-alone"], indent=1)[:4000])
    s_ok = out["P1c__C1S"]["reading"] == "holds" and out["P1c__C2S"]["naming"] == "holds" and out["P1c__C2S"]["held-line fix"] == "works" and out["guards pass"]
    out["shortening verdict"] = "adopt SHORT" if s_ok else "SHORT fails a reading: compare with LONG"
    print("shortening verdict:", out["shortening verdict"])
    (HERE / "p1combined.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview, "run-prod": run_prod,
     "run-iso": lambda: run_iso(sys.argv[2]), "measure": measure}[cmd]()
