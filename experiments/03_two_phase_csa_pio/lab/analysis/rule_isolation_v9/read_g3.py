"""G3 test (user 2026-10-16: "do the g3 test"; decision G3 in V10F_RESULTS.md): do the four adopted facts-first wordings
keep their clarity gain WITHOUT the facts reply format? Code only, read-only on the runs; writes g3_old_format.json.

Question behind it: facts-first has three parts: the rule wording (scope / numbered criteria / outcome), the shared
"Reading a rule" procedure, and a reply format that writes the facts for every part of the rule before each verdict.
The format doubled reply length in the isolation tests. G3 asks whether the full prompt needs it.

Runs compared (all: the 41 modules, each wording, 2 identical repeats, gpt-5.6-luna high, output cap 64,000):
  v10fo   NEW (notebook cell 17): the adopted wordings of Sequencing state, Port options, Clocks and resets and Slices
          (prompt_builds/v10/current_rules.json) with the v10f contexts, in the OLD reply format (isolation.SYSTEM_HEAD).
          Texts and contexts are byte-equal to the facts-format runs (make_v10f_texts.py v10fo stops otherwise), so the
          reply format is the only difference from them.
  facts   each rule's facts-format run of the same text: Sequencing state and Port options v10f, Clocks and resets
          v10f2, Slices v10f3 (isolation.G3_FACTS).
  v10r    the same four rules in the old reply format with their earlier v10 wording and the v10r procedure: the
          baseline the facts-first gain was measured from.
Measure (clarity_unseen.collect = ambiguity_by_rule.measure, unchanged): disagreement rate = signals one run bars and the
other does not / signals either run bars, pooled over modules and wordings (a record and its fields count as one).

Readings set before the run (2026-10-16; cuts chosen here, stated as such):
  O1 (primary; decides G3) the pooled rate of the four rules in v10fo is at most the midpoint between v10r's rate
     (119 / 600 = 0.198) and the facts runs' rate (29 / 456 = 0.064), i.e. 0.131: the old format keeps at least half
     the gain. Both rates are recomputed from the stored runs by the self-test below.
       PASS  -> the wording and the shared procedure carry most of the gain: the full prompt does not need per-signal
                facts in its replies (assemble v10 in its current reply format, with the adopted wordings and the v10f
                procedure).
       FAIL  -> the reply format carries most of the gain: putting facts-first into the full prompt needs its own test
                on the full prompt (longer replies).
       Too close to call: within 2 standard errors of the cut (binomial on v10fo's decided signals; flips cluster by
       module, so the real noise is larger and this band is a lower bound). Too few to tell: under 100 decided signals.
  O2 (read) per rule, the share of its v10r -> facts gain that v10fo keeps: (v10r - v10fo) / (v10r - facts).
  O3 (read; recall risk) reference signals (exact name) barred in both runs, per rule, facts vs v10fo. A rise means
     the rule removes true assets without the facts; watch those signals in the v10 run.
  O4 (read) Phase 1 / Phase 2 stable disagreements summed over the four rules: v10r 20, facts 9 (self-test values).
  O5 (read; the cost side of G3) mean output tokens per reply, reasoning included, per rule: v10fo vs facts vs v10r.
  O6 (read, robustness) O1 with each one rule left out.
Checks chosen AFTER the run (2026-10-16, after reading O1-O6; reported apart, never as readings):
  P1 per rule, reference signals (exact name) barred by one run only and by both runs, v10r / facts / v10fo;
  P2 Sequencing state's bars in the units its scope leaves out (coprocessors cpu_cp_*, and trng), signal-runs per
     phase; known values v9 65 / 65 and v10r 28 / 10 (V10R_RETEST_RESULTS.md) are checked first;
  P3 O1's pooled rate without the one reply that barred every port of pwm (Sequencing state, Phase 2).
What it does not settle: (1) this is the isolation test, not the full prompt; (2) the other 13 rewritten rules were
tested with the v10r procedure, and the v10f procedure drops its "then each exception" and its last clause (decisions
E2, E3); (3) only clarity, not precision or recall (no reference scoring here beyond O3).

Self-test (nothing is reported if it fails):
  - v10r and facts sides reproduce 119 / 600 (P1/P2 20) and 29 / 456 (P1/P2 9), and per wording the flips, stable
    decisions and applied-once counts of compare_v10r.json / compare_v10f.json / compare_v10f2.json / compare_v10f3.json;
  - the decision logic: the facts runs read as the new side PASS, v10r read as the new side FAILS;
  - request identity: for each rule and phase, v10fo's system text equals its facts run's with only the head swapped,
    and its user message is equal (one module checked per rule).

  python -B read_g3.py
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import clarity_unseen as CU  # noqa: E402
import compare_v10r as C  # noqa: E402

RULES = ISO.G3_RULES
NEW = "v10fo"
EXPECT = {"v10r": (119, 600, 20), "facts": (29, 456, 9)}       # measured 2026-10-16 from the stored runs
REPORTS = {"v10r": ("compare_v10r.json", "v10r"), "v10f": ("compare_v10f.json", "v10f"),
           "v10f2": ("compare_v10f2.json", "v10f2"), "v10f3": ("compare_v10f3.json", "v10f3")}


def variant_of(side, rid):
    return ISO.G3_FACTS[rid] if side == "facts" else side


def rates(side):
    """{rule: clarity_unseen.collect row} with each rule read from its own variant."""
    out = {}
    for rid in RULES:
        out.update(CU.collect(variant_of(side, rid), [rid]))
    return out


def pooled(rows, rules=RULES):
    f = sum(rows[r]["flips"] for r in rules if r in rows)
    u = sum(rows[r]["union"] for r in rules if r in rows)
    return f, u, (f / u if u else None)


def decide(old, facts, new, rules=RULES):
    _, _, ro = pooled(old, rules)
    _, _, rf = pooled(facts, rules)
    fn, un, rn = pooled(new, rules)
    cut = (ro + rf) / 2
    if un < 100:
        verdict, se = "too few to tell", None
    else:
        se = math.sqrt(cut * (1 - cut) / un)
        verdict = "PASS" if rn < cut - 2 * se else "FAIL" if rn > cut + 2 * se else "too close to call"
    return {"v10r": round(ro, 3), "facts": round(rf, 3), "cut (midpoint)": round(cut, 3),
            "new": [fn, un, round(rn, 3) if rn is not None else None], "2 SE": round(2 * se, 3) if se else None,
            "verdict": verdict}


def measures(side):
    """compare_v10r.measures over the four rules, each from its own variant (one-sided, applied once, stable on ref)."""
    _, refl = C.CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    prim = Counter()
    for m in ref:
        for r in (0, 1, 2):
            f = ISO.CH.run_dir(ISO.V9, "gpt-5.6-luna", r, "high") / "assets" / f"{m}.json"
            for n in {x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]}:
                prim[(m, n)] += 1
    R, T = {}, {}
    for rid in RULES:
        r, t = C.load(variant_of(side, rid), [rid])
        R.update(r)
        T.update(t)
    return C.measures(R, T, RULES, ref, prim)[0]


def tokens(side):
    """Mean output tokens per stored reply, per rule, and the measured cost."""
    import cost_estimate as CE
    P = CE.PRICES["gpt-5.6-luna"]
    out = {}
    for rid in RULES:
        ISO.use(variant_of(side, rid))
        us = []
        for r in (0, 1):
            for f in ISO.run_root(rep=r).glob(f"P*/{rid}/*.json"):
                u = json.loads(f.read_text(encoding="utf-8")).get("usage") or {}
                if u.get("in") is not None:
                    us.append(u)
        ISO.use("v9")
        if us:
            usd = sum(((u["in"] - (u.get("cached") or 0)) * P["in"] + (u.get("cached") or 0) * P["cached"]
                       + (u.get("out") or 0) * P["out"]) / 1e6 for u in us)
            out[rid] = {"replies": len(us), "mean out": round(sum(u.get("out") or 0 for u in us) / len(us)), "usd": round(usd, 2)}
    return out


def selftest(old, facts, mo, mf):
    bad = []
    for name, rows in (("v10r", old), ("facts", facts)):
        f, u, _ = pooled(rows)
        p = sum(rows[r]["P1/P2"] for r in RULES)
        if (f, u, p) != EXPECT[name]:
            bad.append(f"{name}: {f}/{u}, P1/P2 {p}; expected {EXPECT[name]}")
    for name, meas in (("v10r", mo), ("facts", mf)):
        for rid in RULES:
            v = variant_of(name, rid)
            fname, key = REPORTS[v]
            stored = json.loads((HERE / fname).read_text(encoding="utf-8"))[key][rid]
            for ph in ("P1", "P2"):
                if ph in stored and (meas[rid][ph]["flips"], meas[rid][ph]["stable"], meas[rid][ph]["applied once"]) != (
                        stored[ph]["flips"], stored[ph]["stable"], stored[ph]["applied once"]):
                    bad.append(f"{v} {rid} {ph} differs from {fname}")
            if meas[rid]["P1/P2 stable disagreements"] != stored["P1/P2 stable disagreements"]:
                bad.append(f"{v} {rid} P1/P2 differs from {fname}")
    if decide(old, facts, facts)["verdict"] != "PASS" or decide(old, facts, old)["verdict"] != "FAIL":
        bad.append("decision logic: facts-as-new must PASS and v10r-as-new must FAIL")
    m = "neorv32_wdt"
    ISO.use(NEW)
    to = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    sys_o = {ph: ISO.system(ph) for ph in ("P1", "P2")}
    for rid in RULES:
        v = ISO.G3_FACTS[rid]
        ISO.use(v)
        tf = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
        head = ISO.SYSTEM_HEAD_FACTS2 if ISO.VARIANTS[v].get("head") == "facts2" else ISO.SYSTEM_HEAD_FACTS
        for ph in ("P1", "P2"):
            s = ISO.system(ph)
            if not (s.startswith(head) and sys_o[ph].startswith(ISO.SYSTEM_HEAD) and s[len(head):] == sys_o[ph][len(ISO.SYSTEM_HEAD):]):
                bad.append(f"{rid} {ph}: system text differs from {v} beyond the head")
            if to[rid].get(ph) and ISO.user(m, rid, ph, to) != ISO.user(m, rid, ph, tf):
                bad.append(f"{rid} {ph}: user message differs from {v}")
    ISO.use("v9")
    return bad


OUT_OF_SCOPE = ("neorv32_cpu_cp_", "neorv32_trng")       # units Sequencing state's scope leaves out (P2 below)


def after_the_run(old, facts, new):
    """P1-P3 of the docstring: checks chosen after reading O1-O6, reported apart."""
    import ambiguity_by_rule as AB
    import analyze_isolation as A
    _, refl = C.CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    res = {}
    print("\nAFTER THE RUN (checks chosen after seeing O1-O6, not readings)")
    # P2 first: its known values double as the self-test of the counting
    seq = {}
    for v in ("v9", "v10r", "v10f", NEW):
        R, _ = AB.load(v)
        c = {"P1": [0, 0], "P2": [0, 0]}
        for (rid, ph, m, _r), x in R.items():
            if rid == "P1-15":
                c[ph][0 if m.startswith(OUT_OF_SCOPE) else 1] += len(A.names(x, "barred"))
        seq[v] = c
    if (seq["v9"]["P1"][0], seq["v9"]["P2"][0], seq["v10r"]["P1"][0], seq["v10r"]["P2"][0]) != (65, 65, 28, 10):
        print("  P2 count does not reproduce v9 65/65 and v10r 28/10: nothing reported after the run")
        return {"error": "P2 self-check failed"}
    res["P2 Sequencing state signal-runs barred out of scope | in scope"] = seq
    print("  P2 Sequencing state, signal-runs barred in coprocessors + trng | elsewhere (P1; P2); v9 and v10r reproduce "
          "65/65 and 28/10:", {v: f"P1 {c['P1'][0]}|{c['P1'][1]}  P2 {c['P2'][0]}|{c['P2'][1]}" for v, c in seq.items()})
    # P1 reference signals barred by one run only / both runs
    p1 = {}
    for rid in RULES:
        p1[rid] = {}
        for side in ("v10r", "facts", NEW):
            R, _ = AB.load(variant_of(side, rid))
            one, both, ex = 0, 0, []
            for ph in ("P1", "P2"):
                for m, w in AB.per_wording({k: x for k, x in R.items() if k[0] == rid}, rid, ph).items():
                    for e in sorted((w["D"][0] | w["D"][1]) & ref.get(m, set())):
                        if e in w["D"][0] and e in w["D"][1]:
                            both += 1
                        else:
                            one += 1
                            ex.append(f"{ph} {m.replace('neorv32_', '')}:{e}")
            p1[rid][side] = {"one run only": one, "both runs": both, "one-run examples": ex}
        print(f"  P1 {rid} reference signals barred by one run only | both runs: "
              + "   ".join(f"{s} {p1[rid][s]['one run only']}|{p1[rid][s]['both runs']}" for s in ("v10r", "facts", NEW)))
    print("     Sequencing state one-run reference bars in v10fo:", p1["P1-15"][NEW]["one-run examples"])
    res["P1 reference signals barred by one run only / both runs"] = p1
    # P3 pooled rate without the pwm Phase 2 Sequencing state wording-module
    R, _ = AB.load(NEW)
    w = AB.per_wording({k: x for k, x in R.items() if k[0] == "P1-15"}, "P1-15", "P2").get("neorv32_pwm")
    fn, un, _ = pooled(new)
    f2, u2 = fn - len(w["flips"]), un - len(w["union"])
    res["P3 O1 rate without pwm Phase 2 (Sequencing state)"] = [f2, u2, round(f2 / u2, 3)]
    print(f"  P3 O1 without the pwm Phase 2 Sequencing state module: {f2}/{u2} = {f2 / u2:.3f} (all: {fn}/{un} = {fn / un:.3f})")
    return res


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    old, facts = rates("v10r"), rates("facts")
    mo, mf = measures("v10r"), measures("facts")
    bad = selftest(old, facts, mo, mf)
    print(f"self-test (v10r 119/600 P1/P2 20, facts 29/456 P1/P2 9, per-wording counts = stored reports, decision logic, "
          f"request identity): {'PASS' if not bad else 'FAIL'}")
    for b in bad:
        print("  ", b)
    if bad:
        sys.exit(1)
    ISO.use(NEW)
    stored = sum(1 for r in (0, 1) for _ in ISO.run_root(rep=r).glob("P*/*/*.json"))
    probs = sum(1 for r in (0, 1) for f in ISO.run_root(rep=r).glob("P*/*/*.json")
                if json.loads(f.read_text(encoding="utf-8")).get("problems"))
    expected = len(ISO.jobs(None, reps=(0, 1))[0])
    ISO.use("v9")
    print(f"{NEW}: {stored} of {expected} replies stored, {probs} with format problems")
    if not stored:
        print("nothing to read yet (notebook cell 17)")
        return
    new, mn = rates(NEW), measures(NEW)
    out = {"replies": f"{stored} of {expected}", "format problems": probs, "complete": stored == expected}
    out["O1"] = decide(old, facts, new)
    o1 = out["O1"]
    print(f"\nO1 (primary): pooled rate v10r {o1['v10r']} | facts {o1['facts']} | {NEW} {o1['new'][2]} "
          f"({o1['new'][0]}/{o1['new'][1]}); cut {o1['cut (midpoint)']} +- {o1['2 SE']} -> {o1['verdict']}"
          + ("" if out["complete"] else "   (INCOMPLETE: re-run cell 17)"))
    print(f"\n{'rule':6s} {'title':24s} | rate v10r / facts / {NEW} | gain kept | split/deciding {NEW} | "
          f"P1/P2 v10r/facts/{NEW} | ref barred both runs facts -> {NEW}")
    titles = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    per = {}
    for rid in RULES:
        a, b, c = old[rid], facts[rid], new.get(rid)
        if c is None:
            continue
        gain = a["rate"] - b["rate"]
        kept = round((a["rate"] - c["rate"]) / gain, 2) if gain else None
        rf = sum(mf[rid][ph]["stable on reference (exact)"] for ph in ("P1", "P2") if ph in mf[rid])
        rn = sum(mn[rid][ph]["stable on reference (exact)"] for ph in ("P1", "P2") if ph in mn.get(rid, {}))
        per[rid] = {"title": titles[rid]["title"], "rate v10r / facts / new": [a["rate"], b["rate"], c["rate"]],
                    "O2 gain kept": kept, "split/deciding new": f"{c['split']}/{c['deciding']}",
                    "O4 P1/P2 v10r / facts / new": [a["P1/P2"], b["P1/P2"], c["P1/P2"]],
                    "O3 reference barred in both runs, facts -> new": [rf, rn],
                    "one-sided (left out / other run empty), facts -> new":
                        [[mf[rid][ph]["one-sided (left out / other run empty)"] for ph in ("P1", "P2") if ph in mf[rid]],
                         [mn[rid][ph]["one-sided (left out / other run empty)"] for ph in ("P1", "P2") if ph in mn.get(rid, {})]]}
        p = per[rid]
        print(f"{rid:6s} {p['title'][:24]:24s} | {a['rate']} / {b['rate']} / {c['rate']} | {kept} | {p['split/deciding new']} | "
              f"{a['P1/P2']}/{b['P1/P2']}/{c['P1/P2']} | {rf} -> {rn}")
    out["per rule (O2, O3, O4)"] = per
    out["O4 P1/P2 sum v10r / facts / new"] = [sum(old[r]["P1/P2"] for r in RULES), sum(facts[r]["P1/P2"] for r in RULES),
                                             sum(new[r]["P1/P2"] for r in RULES if r in new)]
    print("O4 Phase 1 / Phase 2 stable disagreements, v10r / facts / new:", out["O4 P1/P2 sum v10r / facts / new"])
    out["O5 output tokens"] = {s: tokens(s) for s in ("v10r", "facts", NEW)}
    print("O5 mean output tokens per reply (replies, mean out, USD):")
    for rid in RULES:
        print(f"   {rid}: " + " | ".join(f"{s} {out['O5 output tokens'][s].get(rid, {}).get('mean out')}" for s in ("v10r", "facts", NEW)))
    o6 = {}
    for rid in RULES:
        rest = [r for r in RULES if r != rid]
        o6[f"without {rid}"] = decide(old, facts, new, rest)
    out["O6 leave one rule out"] = o6
    print("O6 leave one rule out:", {k: f"{v['new'][2]} vs cut {v['cut (midpoint)']}: {v['verdict']}" for k, v in o6.items()})
    out["after the run (chosen after seeing O1-O6)"] = after_the_run(old, facts, new)
    (HERE / "g3_old_format.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nwritten g3_old_format.json")


if __name__ == "__main__":
    main()
