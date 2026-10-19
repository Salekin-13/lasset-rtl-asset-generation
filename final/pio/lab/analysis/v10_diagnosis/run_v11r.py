"""Rule-alone (isolation) test of the revised Phase 1 rule fixes v11r2 on the 26 held-out modules (user 2026-10-17: "Revise
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

VAR = "v11r2"
TEXTS = HERE / "new_rules" / "rule_texts_v11r2.json"
ISO.VARIANTS[VAR] = {"run": "rule_isolation_v11r2", "texts": str(TEXTS),
                     "ctx": (str(ISO.HERE / "context_p1_v10m.md"), str(ISO.HERE / "context_p2_v10m.md"))}
META = json.loads((HERE / "new_rules" / "meta_v11r.json").read_text(encoding="utf-8"))
RULES = ["P1-23", "P1-04", "P1-14", "P1-22", "P1-15"]
CAP_N, CAP_USD = 540, 4.5
OLD = {(rid, ph): ("v12t" if (rid, ph) == ("P1-23", "P1") else "v10r") for rid in RULES for ph in ("P1", "P2")}


def heldout():
    g, refl = RB.CV.groups_and_ref()
    return g["held-out"], {m: set(v) for m, v in refl.items()}


def jobs():
    mods, _ = heldout()
    ISO.use(VAR)
    tx = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    jl = [(rid, ph, m, r) for rid in RULES for ph in ("P1", "P2") for m in mods for r in (0, 1)]
    todo = [j for j in jl if not ISO.path(*j).exists()]
    ISO.use("v9")
    return jl, tx, todo


def old_cost(j):
    """Estimate: the stored cost of the same (rule, phase, module, repeat) cell in the old run; mean if missing."""
    rid, ph, m, r = j
    ISO.use(OLD[(rid, ph)])
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
    p = str(L.LAB / "runs" / "rule_isolation_v11r2" / f"{MODEL}__{EFFORT}")
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
    sys.stdout.reconfigure(encoding="utf-8")
    if not selftest(log=print):
        sys.exit("self-test FAIL; nothing reported")
    mods, ref = heldout()
    hos = {m[8:] for m in mods}
    tx = json.loads(TEXTS.read_text(encoding="utf-8"))
    out = {}
    for rid in RULES:
        tcases = [c for c in targeted(rid) if c.split(":")[0] in hos]
        untested = [c for c in targeted(rid) if c.split(":")[0] not in hos]
        for ph in ("P1", "P2"):
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
            good, expl, notcov = 0, 0, []
            for case in tcases:
                mm, e = "neorv32_" + case.split(":")[0], case.split(":", 1)[1]
                if mm not in cons_b:
                    notcov.append(case + " (no replies)")
                    continue
                reps = cons_b[mm][1]
                barred = any(RB.down(e, AN.names(x, "barred")) for x in reps)
                good += not barred
                expl += all(e in AN.names(x, "spared") for x in reps)
                if barred:
                    notcov.append(case)
            all_ref_barred = sorted(f"{m[8:]}:{e}" for m, (cons, _) in cons_b.items() for e in ref[m] if RB.down(e, cons))
            nb, ns, kept, tot = compare(OLD[(rid, ph)], VAR, rid, ph, mods, ref)
            cov = round(good / len(tcases), 3) if tcases else None
            row = {"title": tx[rid]["title"], "old text run": OLD[(rid, ph)],
                   "modules deciding something": len(dis), "mean disagreement": mean, "contradiction modules": contra,
                   "ambiguity PASS": mean <= RV.CUT_DIS and len(contra) <= 1,
                   "targeted cases (held-out)": len(tcases), "not barred in either repeat": good, "explicitly spared in both": expl,
                   "coverage": cov, "coverage PASS": cov is None or cov >= RV.CUT_COV, "barred targeted cases": notcov,
                   "targeted cases in tuning modules (untested)": untested,
                   "reference entries barred in both repeats": all_ref_barred, "newly barred reference entries": nb,
                   "harm PASS": not nb,
                   "boundary: old non-reference bars still barred in both": f"{kept}/{tot}", "boundary: newly spared non-reference": ns,
                   "missing replies": missing}
            out[f"{rid} {ph}"] = row
        out[rid] = {"PASS": all(out[f"{rid} {ph}"][k] for ph in ("P1", "P2") for k in ("ambiguity PASS", "harm PASS", "coverage PASS"))}
    (HERE / "read_v11r2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, r in out.items():
        if " " in k:
            print(f"{k:8s} {r['title'][:24]:24s} dis {r['mean disagreement']:.3f} ({r['modules deciding something']} mods) contra {len(r['contradiction modules'])} "
                  f"| cov {r['not barred in either repeat']}/{r['targeted cases (held-out)']} | newly barred ref {len(r['newly barred reference entries'])} "
                  f"| old bars kept {r['boundary: old non-reference bars still barred in both']} newly spared {len(r['boundary: newly spared non-reference'])} "
                  f"| amb {'ok' if r['ambiguity PASS'] else 'FAIL'} harm {'ok' if r['harm PASS'] else 'FAIL'} cov {'ok' if r['coverage PASS'] else 'FAIL'}")
    print("PASS per rule:", {k: v["PASS"] for k, v in out.items() if " " not in k})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"selftest": lambda: sys.exit(0 if selftest() else 1), "preview": preview, "run": run, "measure": measure}[sys.argv[1]]()
