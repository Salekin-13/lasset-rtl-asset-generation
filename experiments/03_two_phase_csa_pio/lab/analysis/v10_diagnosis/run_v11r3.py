"""v11r3 re-test (planned 2026-10-17, PLAN_V11R3_RETEST.md; not sent without the user's go-ahead): the failing wordings of v11r2
after the cause readers' rewordings (make_v11r3.py), only on the held-out modules where each wording decided something
(v11r3_retest_cells.json). Option "p1" = the four Phase 1 wordings; option "all" = all seven. Built from run_v11r.py:

Rule-alone (isolation) test of the revised Phase 1 rule fixes v11r2 on the 26 held-out modules (user 2026-10-17: "Revise
the 22 flagged two-way phrases in the v11r drafts (one Claude round), re-run the checker, then send the luna rule-alone
test on the 26 held-out modules (both phases, r0-r1, cap USD 4.5) with the readings in P1_RULE_FIXES.md, and report.").

Texts: new_rules/rule_texts_v11r2.json (v11r after the revision round wf_8d989bb1-219); meta new_rules/meta_v11r.json
(intent, expected spared and still barred). Five rules, each a revision of the v11h wording: P1-23 Access command
fields, P1-04 Pacing pulses, P1-14 Port buffers, P1-22 Operation selectors, P1-15 Sequencing state.
Format: the isolation format (old reply format: barred / spared / unsure), luna, high, max_tokens 64,000, in the v10m
context (v10's core with the merged procedure = v11h's "Reading a rule" sentence, no other rule), as for N01-N15.
Requests: 5 rules x 2 phases x 26 held-out modules x r0-r1 = 520. Cap: 540 requests, USD 4.5.

Readings (P1_RULE_FIXES.md, set before sending; the definitions below are written 2026-10-17 before any call):
  ambiguity  per wording: mean per-module disagreement <= 0.157 and contradictions in <= 1 module (read_v11n.decide,
             the D13 cuts; records and their fields counted as one).
  coverage   per wording: the targeted intended cases (meta expected_spared, among the meta intended cases, in a
             held-out module) NOT barred in either repeat; share >= 0.8. "Spared" in the plan = not barred (the rule may
             also simply not name it); the explicitly spared count is printed beside it.
  harm       per wording: reference entries barred in both repeats that the old text did NOT bar in both repeats
             ("newly barred"): 0. All reference entries barred in both repeats are listed too.
  boundary   per wording: non-reference elements the old text barred in both repeats: how many the new text still bars
             in both repeats; the ones it no longer bars in either repeat are listed ("newly spared"). Read only.
  Old text = the stored rule-alone runs: v10r (context_p*_v10r: same core, the "Reading a rule" sentence 5 words
  shorter) for every wording except Access command fields Phase 1, whose old text is the carried F1 text; its closest
  tested form is v12t (474 words, context v10u). Stated in the report as a confound.
  PASS per rule = both wordings pass ambiguity, harm and coverage. Not measured: tuning modules (the targeted cases there
  are untested), the full prompt.

  python -B run_v11r.py selftest
  python -B run_v11r.py preview
  <conda python> run_v11r.py run
  python -B run_v11r.py measure        (writes read_v11r2.json)
"""
import json
import os
import re
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, MODEL, EFFORT, register  # noqa: E402

ISO = register()
import chain as CH  # noqa: E402
import analyze_isolation as AN  # noqa: E402
import rule_breaks as RB  # noqa: E402
import ladder as L  # noqa: E402
import run_a  # noqa: E402
import read_v11n as RV  # noqa: E402
import check_new_rules as CN  # noqa: E402
import meta_tools as mt  # noqa: E402
import p1tighten  # noqa: E402,F401  (registers v12t)
import run_v11q  # noqa: E402,F401  (registers v11q, the N11-N15 test in the same context)
import run_v11r as R2  # noqa: E402  (registers v11r2, the run these wordings revise)

VAR = "v11r3"
TEXTS = HERE / "new_rules" / "rule_texts_v11r3.json"
ISO.VARIANTS[VAR] = {"run": "rule_isolation_v11r3", "texts": str(TEXTS),
                     "ctx": (str(ISO.HERE / "context_p1_v10m.md"), str(ISO.HERE / "context_p2_v10m.md"))}
META = json.loads((HERE / "new_rules" / "meta_v11r.json").read_text(encoding="utf-8"))
RULES = ["P1-23", "P1-04", "P1-14", "P1-22", "P1-15"]
CELLS = json.loads((HERE / "v11r3_retest_cells.json").read_text(encoding="utf-8"))
OPTION = os.environ.get("V11R3_OPTION", "p1")
WORDINGS = [k for k in CELLS if OPTION == "all" or k.endswith(" P1")]
CAP_N, CAP_USD = (120, 1.9) if OPTION == "p1" else (200, 3.2)
OLD = {(rid, ph): ("v12t" if (rid, ph) == ("P1-23", "P1") else "v10fo" if rid == "P1-15" else "v10r") for rid in RULES for ph in ("P1", "P2")}   # each wording's last old-format run (isolation.E3_LAST)


def heldout():
    g, refl = RB.CV.groups_and_ref()
    return g["held-out"], {m: set(v) for m, v in refl.items()}


def jobs():
    mods, _ = heldout()
    ISO.use(VAR)
    tx = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    jl = [(w.split()[0], w.split()[1], "neorv32_" + m, r) for w in WORDINGS for m in CELLS[w]["modules"] for r in (0, 1)]
    todo = [j for j in jl if not ISO.path(*j).exists()]
    ISO.use("v9")
    return jl, tx, todo


def old_cost(j):
    """Estimate: the stored cost of the same (rule, phase, module, repeat) cell in the v11r2 run; mean if missing."""
    rid, ph, m, r = j
    ISO.use("v11r2")
    f = ISO.run_root(rep=r) / ph / rid / f"{m}.json"
    ISO.use("v9")
    if f.exists():
        u = json.loads(f.read_text(encoding="utf-8")).get("usage")
        if u and u.get("in") is not None:
            return run_a.usd(u)
    return None


def estimate(todo):
    c = [old_cost(j) for j in todo]
    known = [x for x in c if x is not None]
    mean = sum(known) / len(known) if known else 0.0075
    return sum(known) + mean * (len(c) - len(known)), len(c) - len(known)


def selftest(log=print):
    c = {}
    ISO.use(VAR)
    tx = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    s_new = {ph: CH.sha12(ISO.system(ph)) for ph in ("P1", "P2")}
    m = "neorv32_cpu_counters"
    u = ISO.user(m, "P1-23", "P1", tx)
    ISO.use("v11q")
    s_q = {ph: CH.sha12(ISO.system(ph)) for ph in ("P1", "P2")}
    ISO.use("v9")
    c["v11r2 uses the v10m context (same system text as v11q, N11-N15)"] = s_new == s_q
    c["5 rules, each with P1 and P2 text"] = sorted(tx) == sorted(RULES) and all(tx[r].get("P1") and tx[r].get("P2") for r in RULES)
    c["the P1-23 P1 request carries its rule text"] = tx["P1-23"]["P1"].split("\n")[1].strip() in u
    c["all texts pass check_new_rules and meta_tools.check_prompt"] = all(
        not CN.check_text(r, ph, tx[r][ph]) and not mt.check_prompt(tx[r][ph], CN.names(), r)["problems"] for r in RULES for ph in ("P1", "P2"))
    mods, _ = heldout()
    c["26 held-out modules, each with inputs"] = len(mods) == 26 and all((CH.module_dir(mm) / "rtl.txt").exists() for mm in mods)
    c["isolation self-test"] = ISO.selftest(log=lambda *a: None)
    c["reader self-test (planted pair; old run against itself: 0 newly barred, 0 newly spared)"] = RV.selftest() and _self_compare()
    bad = [k for k, ok in c.items() if not ok]
    log(f"run_v11r self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


def replies(var, rid, ph, m):
    ISO.use(var)
    out = []
    for r in (0, 1):
        f = ISO.run_root(rep=r) / ph / rid / f"{m}.json"
        rec = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        out.append(rec.get("reply") if rec and isinstance(rec.get("reply"), dict) else None)
    ISO.use("v9")
    return out


def bars_both(reps, m):
    if any(x is None for x in reps):
        return None
    b = [AN.names(x, "barred") for x in reps]
    return {e for (_, e) in CH.closed_names(m) if RB.down(e, b[0]) and RB.down(e, b[1])}


def bars_any(reps, m):
    b = set()
    for x in reps:
        if x is not None:
            b |= AN.names(x, "barred")
    return {e for (_, e) in CH.closed_names(m) if RB.down(e, b)}


def compare(old_var, new_var, rid, ph, mods, ref):
    newly_barred, newly_spared, kept, old_nonref = [], [], 0, 0
    for m in mods:
        ob, nb = bars_both(replies(old_var, rid, ph, m), m), bars_both(replies(new_var, rid, ph, m), m)
        if ob is None or nb is None:
            continue
        na = bars_any(replies(new_var, rid, ph, m), m)
        newly_barred += [f"{m[8:]}:{e}" for e in sorted(nb - ob) if e in ref[m]]
        for e in ob:
            if e not in ref[m]:
                old_nonref += 1
                kept += e in nb
                if e not in na:
                    newly_spared.append(f"{m[8:]}:{e}")
    return newly_barred, newly_spared, kept, old_nonref


def _self_compare():
    mods, ref = heldout()
    nb, ns, kept, tot = compare("v10r", "v10r", "P1-14", "P1", mods, ref)
    return not nb and not ns and kept == tot and tot > 0


def preview():
    if not selftest():
        sys.exit("self-test FAIL")
    jl, tx, todo = jobs()
    est, unknown = estimate(todo)
    print(f"{len(todo)} requests to send (of {len(jl)}); about USD {est:.2f} (the old runs' stored cost of the same cells; "
          f"{unknown} cells estimated by the mean); cap {CAP_N} requests / USD {CAP_USD}")
    print(f"spent so far USD {run_a.spent(log=lambda *a: None):.2f}")


def run():
    if not selftest(log=lambda *a: None):
        sys.exit("self-test FAIL; nothing sent")
    jl, tx, todo = jobs()
    est, _ = estimate(todo)
    if len(todo) > CAP_N or est > CAP_USD:
        sys.exit(f"{len(todo)} requests, about USD {est:.2f}: over the cap; nothing sent")
    ex = json.loads(L.EXTRA.read_text(encoding="utf-8")) if L.EXTRA.exists() else []
    p = str(L.LAB / "runs" / "rule_isolation_v11r3" / f"{MODEL}__{EFFORT}")
    if p not in ex:
        L.EXTRA.write_text(json.dumps(ex + [p], indent=1), encoding="utf-8")
    start = run_a.spent(log=lambda *a: None)
    print(f"sending {len(todo)} (about USD {est:.2f}); spent before USD {start:.2f}")
    ISO.use(VAR)
    ISO.run(todo, tx, lambda out: CH.openai(MODEL, EFFORT, out=out, poll=5, max_tokens=64000), MODEL, EFFORT, workers=50)
    ISO.use("v9")
    left = jobs()[2]
    print(f"not stored: {len(left)}; spent this run USD {run_a.spent(log=lambda *a: None) - start:.3f}")


def targeted(rid):
    m = META[rid]
    intended = set(m["intended (v9 misses citing the rule, and reference entries the rule bars alone)"])
    sp = {re.split(r"[\s(]", s.strip())[0] for s in m["expected_spared"]}
    return sorted(sp & intended)


def measure():
    """Readings (PLAN_V11R3_RETEST.md, set before sending), per re-tested wording, over its re-test modules only:
    ambiguity (D13 cuts, read_v11n.decide), coverage (targeted held-out cases not barred in either repeat), harm (reference
    entries barred in both repeats that the old text did not bar in both), boundary (old non-reference bars still barred),
    and the same harm / boundary against v11r2 (read only). Modules outside the re-test cells are not measured."""
    sys.stdout.reconfigure(encoding="utf-8")
    if not selftest(log=print):
        sys.exit("self-test FAIL; nothing reported")
    _, ref = heldout()
    tx = json.loads(TEXTS.read_text(encoding="utf-8"))
    out = {}
    for w in WORDINGS:
        rid, ph = w.split()
        mods = ["neorv32_" + m for m in CELLS[w]["modules"]]
        hos = set(CELLS[w]["modules"])
        tcases = [c for c in targeted(rid) if c.split(":")[0] in hos]
        dis, contra, missing, cons_b = [], [], [], {}
        for m in mods:
            reps = replies(VAR, rid, ph, m)
            if any(x is None for x in reps):
                missing.append(m[8:])
                continue
            d, c, cons, _ = RV.decide(reps, keep=False)
            if d is not None:
                dis.append(d)
            if c:
                contra.append(m[8:])
            cons_b[m] = (cons, reps)
        mean = round(sum(dis) / len(dis), 3) if dis else 0.0
        good, notcov = 0, []
        for case in tcases:
            mm, e = "neorv32_" + case.split(":")[0], case.split(":", 1)[1]
            if mm not in cons_b:
                notcov.append(case + " (no replies)")
                continue
            barred = any(RB.down(e, AN.names(x, "barred")) for x in cons_b[mm][1])
            good += not barred
            if barred:
                notcov.append(case)
        nb, ns, kept, tot = compare(OLD[(rid, ph)], VAR, rid, ph, mods, ref)
        nb2, ns2, kept2, tot2 = compare("v11r2", VAR, rid, ph, mods, ref)
        cov = round(good / len(tcases), 3) if tcases else None
        out[w] = {"title": tx[rid]["title"], "modules": len(mods), "modules deciding something": len(dis), "mean disagreement": mean,
                  "contradiction modules": contra, "ambiguity PASS": mean <= RV.CUT_DIS and len(contra) <= 1,
                  "targeted cases": len(tcases), "not barred in either repeat": good, "coverage": cov,
                  "coverage PASS": cov is None or cov >= RV.CUT_COV, "barred targeted cases": notcov,
                  "old text run": OLD[(rid, ph)], "newly barred reference (vs old)": nb, "harm PASS": not nb,
                  "boundary vs old: kept": f"{kept}/{tot}", "newly spared non-reference (vs old)": ns,
                  "newly barred reference (vs v11r2, read only)": nb2, "boundary vs v11r2: kept": f"{kept2}/{tot2}",
                  "newly spared non-reference (vs v11r2, read only)": ns2, "missing replies": missing}
        out[w]["PASS"] = out[w]["ambiguity PASS"] and out[w]["harm PASS"] and out[w]["coverage PASS"]
    (HERE / "read_v11r3.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for w, r in out.items():
        print(f"{w:8s} {r['title'][:22]:22s} dis {r['mean disagreement']:.3f} ({r['modules deciding something']} of {r['modules']}) contra {len(r['contradiction modules'])} "
              f"| cov {r['not barred in either repeat']}/{r['targeted cases']} | newly barred ref {len(r['newly barred reference (vs old)'])} "
              f"| kept {r['boundary vs old: kept']} | {'PASS' if r['PASS'] else 'FAIL'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview, "run": run, "measure": measure}[sys.argv[1]]()
