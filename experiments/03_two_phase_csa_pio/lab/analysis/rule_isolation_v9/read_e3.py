"""E3 re-test (user 2026-10-16: "Use the merged procedure. Build the E3 re-test of all 17 rules (old reply format, send
switch off) with readings set before the run"). Does the merged "Reading a rule" procedure that v10 will carry make any
of the 17 re-tested rules less clear than the procedure it was last tested with? Code only, read-only on the runs;
writes e3_<new>.json.

Sides (same rule texts, same old reply format, same 41 modules, 2 identical repeats each):
  new     "v10m": the merged procedure (prompt_builds/v10/make_v10.py PROC) in the context (make_v10m_texts.py).
  last    each rule's last old-format test: the 13 v10 rewrites from "v10r" (v10r procedure, with the clause E2 drops),
          the 4 adopted facts-first rules from "v10fo" (v10f procedure; the G3 test). isolation.E3_LAST.
The texts are byte-equal between the sides, so the procedure sentence is the only difference.
Measures (unchanged code): disagreement rate (ambiguity_by_rule.measure: signals one run bars and the other does not /
signals either run bars, a record and its fields counted as one), Phase 1 / Phase 2 stable disagreements
(analyze_isolation), applied-once modules, reference signals (exact name) barred in one or both runs (compare_v10r.measures),
and the code-defined pattern of Second copies (pattern_coverage, detector ("P1", "COPY"), 14 signals).
A side can be run on another executor (e.g. a Claude paired run): main(new=..., last=..., modules=...) compares any
two sides on the modules given; never mix executors between the two sides.

Readings set before the run (2026-10-16; cuts chosen here, stated as such):
  E3-1 (primary; decides whether v10 carries the merged procedure) the pooled disagreement rate of the 17 rules under
       the new procedure is at most the last tests' pooled rate plus 2 standard errors (binomial at the last tests'
       rate, on the new side's decided signals; flips cluster by module, so this band is a lower bound on the noise).
         PASS -> the merged procedure costs no clarity: assemble v10 with it.
         FAIL -> it makes rules less clear: read E3-2 / E3-3 to see which group, before assembling anything.
       Too few to tell under 100 decided signals.
  E3-2 (read) the 13 v10 rewrites: v10r -> new, pooled and per rule (the change for them: the E2 clause dropped,
       "it lists", the "only / every" check).
  E3-3 (read) the 4 adopted rules: v10fo -> new, pooled and per rule (the change for them: an exception step that is
       empty for them, "against the RTL" for "writing the RTL fact", "check" for "list").
  E3-4 (read; tests E2's reasoning, not measured before) Second copies' code-defined pattern barred in both runs, per
       wording: v9 13 / 11 of 14, v10r 6 / 8 of 14. E2's reasoning (the clause made runs skip signals the rule covers)
       is supported if the new side bars more of the pattern than v10r in both wordings.
  E3-5 (read) applied-once modules summed over the 17 rules (one run decides something, the other nothing).
  E3-6 (read; recall risk) reference signals (exact name) barred by one run only and by both runs, summed.
  E3-7 (read) Phase 1 / Phase 2 stable disagreements summed.
  E3-8 (read; the G3 watch list, user 2026-10-16) of Sequencing state's 17 reference signals (19 signal-wordings) that one v10fo run
       barred, how many any new run bars.
  E3-9 (read, robustness) E3-1 with each one rule left out.
What it does not settle: the full prompt (v10's run on tuning_v2 / heldout_v2 does); precision and recall.

Claude run (2026-10-16, user: "test it here, as I do not have openai budget"; claude_e3.py; written before the full run,
after only the format of the 2 pilot replies was checked): the same readings E3-1 ... E3-9, with new = "v10m__claude",
last = "v10r__claude" (13 rules) / "v10fo__claude" (4 rules), on claude_e3.MODULES (uart, twi, wdt, xbus) only.
E3-4 compares the two Claude sides (the v9 / v10r values are luna's and are shown for context only); E3-8 can only see the
3 wdt signals of the watch list. Rules are batched per group in one call on both sides (claude_e3.py docstring).
  python -B read_e3.py claude

Self-test (nothing is reported if it fails):
  - the last sides reproduce the stored reports: v10r per wording (flips, stable, applied once, P1/P2) = compare_v10r.json;
    v10fo per rule (rate, P1/P2) = g3_old_format.json;
  - Second copies' pattern: v9 13 / 11 and v10r 6 / 8 of 14 = compare_v10r.json R3;
  - decision logic: the last sides read as new PASS; v9 read as new (known less clear) FAILS;
  - request identity: v10m's system text equals v10r's with only the procedure replaced, and every user message
    equals its last test's (one module checked per rule).

  python -B read_e3.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prompt_builds" / "v10"))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402
import ambiguity_by_rule as AB  # noqa: E402
import compare_v10r as C  # noqa: E402

RULES = ISO.RULES17
G3_WATCH = {"neorv32_wdt": {"cnt", "cnt_timeout", "reset_wdt"},
            "neorv32_pwm": {"cfg_cdiv", "cfg_en", "cfg_prsc", "clkgen_en_o", "clkgen_i", "pwm_o", "we_i"},
            "neorv32_bus": {"keeper.cnt", "keeper.err", "keeper.halt"}, "neorv32_debug_dm": {"dm_ctrl.busy"},
            "neorv32_cpu_lsu": {"mar"}, "neorv32_cpu_cp_shifter": {"shifter.cnt", "shifter.done_ff"}}


def load(side, rules, modules=None):
    """Replies of a side: side is a variant name, or a {rule: variant} map (each rule from its own test)."""
    R, T = {}, {}
    for rid in rules:
        v = side[rid] if isinstance(side, dict) else side
        r, t = AB.load(v)
        R.update({k: x for k, x in r.items() if k[0] == rid and (modules is None or k[2] in modules)})
        if rid in t:
            T[rid] = t[rid]
    return R, T


def rows(R, rules):
    """Per rule: flips, union, rate, P1/P2, applied once (as clarity_unseen.collect, on any reply set)."""
    rep = A.analyze(R, None, {})
    out = {}
    for rid in rules:
        if rid not in rep:
            continue
        row = {"flips": 0, "union": 0, "applied once": 0, "P1/P2": len(rep[rid]["Phase 1 / Phase 2 stable disagreements"])}
        for ph in ("P1", "P2"):
            if ph in rep[rid]:
                x = AB.measure(R, None, rep, rid, ph)
                row[ph] = {k: v for k, v in x.items() if not k.startswith("_")}
                row["flips"] += x["flips"]
                row["union"] += x["decided (union)"]
                row["applied once"] += x["applied once"]
        row["rate"] = round(row["flips"] / row["union"], 3) if row["union"] else None
        out[rid] = row
    return out


def pooled(rw, rules):
    f = sum(rw[r]["flips"] for r in rules if r in rw)
    u = sum(rw[r]["union"] for r in rules if r in rw)
    return f, u, (f / u if u else None)


def decide(last, new, rules):
    fl, ul, rl = pooled(last, rules)
    fn, un, rn = pooled(new, rules)
    if not un or un < 100 or rl is None:
        return {"last": [fl, ul, rl], "new": [fn, un, rn], "verdict": "too few to tell"}
    band = 2 * math.sqrt(rl * (1 - rl) / un)
    return {"last": [fl, ul, round(rl, 3)], "new": [fn, un, round(rn, 3)], "bar (last + 2 SE)": round(rl + band, 3),
            "verdict": "PASS" if rn <= rl + band else "FAIL"}


def reference():
    _, refl = C.CV.groups_and_ref()
    return {m: set(v) for m, v in refl.items()}


def ref_barred(R, rules, ref):
    """Reference signals (exact name) barred by one run only / by both runs, summed over rules and wordings."""
    one = both = 0
    for rid in rules:
        for ph in ("P1", "P2"):
            for m, w in AB.per_wording({k: x for k, x in R.items() if k[0] == rid}, rid, ph).items():
                for e in (w["D"][0] | w["D"][1]) & ref.get(m, set()):
                    if e in w["D"][0] and e in w["D"][1]:
                        both += 1
                    else:
                        one += 1
    return one, both


def copy_pattern(R, modules=None):
    """Second copies' code-defined pattern ("P1", "COPY"): signals barred in both runs, per wording."""
    import pattern_coverage as PC
    hits, _, _ = PC.scan()
    inst = {(m, n) for fx, t, m, en, n in hits if (fx, t[0] if fx == "P3" else t) == ("P1", "COPY")
            and (modules is None or m in modules)}
    out = {}
    for ph in ("P1", "P2"):
        n = 0
        for m, e in inst:
            if all((("P1-06", ph, m, r) in R) and A.covered(e, A.names(R[("P1-06", ph, m, r)], "barred")) for r in (0, 1)):
                n += 1
        out[ph] = n
    return out, len(inst)


def selftest():
    bad = []
    last = ISO.E3_LAST
    R9, _ = load("v9", RULES)
    RL, _ = load(last, RULES)
    rl = rows(RL, RULES)
    c10 = json.loads((HERE / "compare_v10r.json").read_text(encoding="utf-8"))["v10r"]
    for rid in RULES:
        if last[rid] != "v10r":
            continue
        for ph in ("P1", "P2"):
            if ph in c10[rid] and (rl[rid][ph]["flips"], rl[rid][ph]["stable"], rl[rid][ph]["applied once"]) != (
                    c10[rid][ph]["flips"], c10[rid][ph]["stable"], c10[rid][ph]["applied once"]):
                bad.append(f"v10r {rid} {ph} differs from compare_v10r.json")
        if rl[rid]["P1/P2"] != c10[rid]["P1/P2 stable disagreements"]:
            bad.append(f"v10r {rid} P1/P2 differs from compare_v10r.json")
    g3 = json.loads((HERE / "g3_old_format.json").read_text(encoding="utf-8"))["per rule (O2, O3, O4)"]
    for rid in ISO.G3_RULES:
        if (rl[rid]["rate"], rl[rid]["P1/P2"]) != (g3[rid]["rate v10r / facts / new"][2], g3[rid]["O4 P1/P2 v10r / facts / new"][2]):
            bad.append(f"v10fo {rid} differs from g3_old_format.json")
    r3 = json.loads((HERE / "compare_v10r.json").read_text(encoding="utf-8"))["R3 patterns barred in both runs"]
    cp9, n9 = copy_pattern(R9)
    cp10, _ = copy_pattern(load("v10r", ["P1-06"])[0])
    want = (r3["register copying another register (P1)"]["v9"], r3["register copying another register (P2)"]["v9"],
            r3["register copying another register (P1)"]["v10r"], r3["register copying another register (P2)"]["v10r"], 14)
    if (cp9["P1"], cp9["P2"], cp10["P1"], cp10["P2"], n9) != want or want[:4] != (13, 11, 6, 8):
        bad.append(f"Second copies pattern {cp9} {cp10} of {n9}, expected {want}")
    r9 = rows(R9, RULES)
    if decide(rl, rl, RULES)["verdict"] != "PASS" or decide(rl, r9, RULES)["verdict"] != "FAIL":
        bad.append("decision logic: last-as-new must PASS and v9-as-new must FAIL")
    import make_v10 as MV
    ISO.use("v10m")
    tm = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
    sm = {ph: ISO.system(ph) for ph in ("P1", "P2")}
    ISO.use("v10r")
    sr = {ph: ISO.system(ph) for ph in ("P1", "P2")}
    if sr["P1"].replace(MV.PROC_V10R_P1, MV.PROC_P1) != sm["P1"] or sr["P2"].replace(MV.PROC_V10R_P2, MV.PROC_P2) != sm["P2"] \
            or sm["P1"] == sr["P1"]:
        bad.append("v10m system text differs from v10r's beyond the procedure")
    for rid in RULES:
        ISO.use(last[rid])
        tv = json.loads(ISO.texts_file().read_text(encoding="utf-8"))
        for ph in ("P1", "P2"):
            if tm[rid].get(ph) and ISO.user("neorv32_wdt", rid, ph, tm) != ISO.user("neorv32_wdt", rid, ph, tv):
                bad.append(f"{rid} {ph}: user message differs from {last[rid]}")
    ISO.use("v9")
    return bad, rl


def main(new="v10m", last=None, modules=None, tag=None):
    sys.stdout.reconfigure(encoding="utf-8")
    last = last or ISO.E3_LAST
    bad, _ = selftest()
    print("self-test (last sides = stored reports, Second copies pattern 13/11 and 6/8 of 14, decision logic, request "
          f"identity): {'PASS' if not bad else 'FAIL'}")
    for b in bad:
        print("  ", b)
    if bad:
        sys.exit(1)
    RN, _ = load(new, RULES, modules)
    if not RN:
        print(f"{new}: no replies stored yet")
        return
    mods = sorted({k[2] for k in RN}) if modules is None else sorted(modules)
    RL, _ = load(last, RULES, mods)
    keys_n = {k for k in RN}
    keys_l = {k for k in RL}
    common = keys_n & keys_l
    RN = {k: v for k, v in RN.items() if k in common}
    RL = {k: v for k, v in RL.items() if k in common}
    print(f"{new}: {len(keys_n)} replies; compared on {len(common)} (rule, wording, module, repeat) keys present on both sides, "
          f"{len(mods)} modules")
    ln, nn = rows(RL, RULES), rows(RN, RULES)
    out = {"compared keys": len(common), "modules": mods}
    out["E3-1"] = decide(ln, nn, RULES)
    e = out["E3-1"]
    print(f"\nE3-1 (primary): pooled rate last {e['last'][2]} ({e['last'][0]}/{e['last'][1]}) -> new {e['new'][2]} "
          f"({e['new'][0]}/{e['new'][1]}); bar {e.get('bar (last + 2 SE)')} -> {e['verdict']}")
    g13 = [r for r in RULES if r not in ISO.G3_RULES]
    g4 = [r for r in RULES if r not in g13]
    for name, grp in (("E3-2 the 13 v10 rewrites", g13), ("E3-3 the 4 adopted rules", g4)):
        a, b = pooled(ln, grp), pooled(nn, grp)
        out[name] = {"last": [a[0], a[1], round(a[2], 3) if a[2] is not None else None],
                     "new": [b[0], b[1], round(b[2], 3) if b[2] is not None else None]}
        print(f"{name}: {out[name]['last']} -> {out[name]['new']}")
    titles = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    per = {}
    print(f"\n{'rule':6s} {'title':30s} last test | rate last -> new | split/deciding new | applied once last -> new | P1/P2 last -> new")
    for rid in RULES:
        a, b = ln.get(rid), nn.get(rid)
        if not a or not b:
            continue
        sd = sum(b[ph]["split modules"] for ph in ("P1", "P2") if ph in b), sum(b[ph]["deciding"] for ph in ("P1", "P2") if ph in b)
        per[rid] = {"title": titles[rid]["title"], "last test": last[rid] if isinstance(last, dict) else last,
                    "rate": [a["rate"], b["rate"]], "split/deciding new": list(sd),
                    "applied once": [a["applied once"], b["applied once"]], "P1/P2": [a["P1/P2"], b["P1/P2"]]}
        p = per[rid]
        print(f"{rid:6s} {p['title'][:30]:30s} {p['last test']:9s} | {a['rate']} -> {b['rate']} | {sd[0]}/{sd[1]} | "
              f"{a['applied once']} -> {b['applied once']} | {a['P1/P2']} -> {b['P1/P2']}")
    out["per rule"] = per
    cl, nl = copy_pattern(RL, mods)
    cn, ni = copy_pattern(RN, mods)
    out["E3-4 Second copies pattern barred in both runs (P1, P2)"] = {"last (v10r)": cl, "new": cn, "of": ni,
                                                                      "supports E2": cn["P1"] > cl["P1"] and cn["P2"] > cl["P2"]}
    print(f"\nE3-4 Second copies pattern barred in both runs: v10r {cl} -> new {cn} of {ni} (v9 13 / 11 of 14 on all 41)")
    out["E3-5 applied once"] = [sum(ln[r]["applied once"] for r in ln), sum(nn[r]["applied once"] for r in nn)]
    ref = reference()
    out["E3-6 reference barred one run / both runs"] = {"last": ref_barred(RL, RULES, ref), "new": ref_barred(RN, RULES, ref)}
    out["E3-7 P1/P2"] = [sum(ln[r]["P1/P2"] for r in ln), sum(nn[r]["P1/P2"] for r in nn)]
    tot = sum(len(v) for m, v in G3_WATCH.items() if m in mods)
    hit = set()
    for (rid, ph, m, r), x in RN.items():
        if rid == "P1-15" and m in G3_WATCH:
            for e in A.names(x, "barred") & G3_WATCH[m]:
                hit.add((m, e))
    out["E3-8 G3 watch list barred by any new run"] = [len(hit), tot, sorted(f"{m.replace('neorv32_', '')}:{e}" for m, e in hit)]
    print("E3-5 applied-once modules last -> new:", out["E3-5 applied once"])
    print("E3-6 reference signals barred (one run, both runs) last -> new:", out["E3-6 reference barred one run / both runs"])
    print("E3-7 Phase 1 / Phase 2 stable disagreements last -> new:", out["E3-7 P1/P2"])
    print(f"E3-8 G3 watch list (Sequencing state): {len(hit)} of {tot} barred by any new run: {out['E3-8 G3 watch list barred by any new run'][2]}")
    out["E3-9 leave one rule out"] = {f"without {r}": decide(ln, nn, [x for x in RULES if x != r])["verdict"] for r in RULES}
    print("E3-9 leave one rule out:", out["E3-9 leave one rule out"])
    (HERE / f"e3_{tag or new}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten e3_{tag or new}.json")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "claude":
        import claude_e3 as CE3
        main(new="v10m__claude", last={r: ("v10fo__claude" if r in ISO.G3_RULES else "v10r__claude") for r in RULES},
             modules=CE3.MODULES, tag="claude")
    else:
        main()
