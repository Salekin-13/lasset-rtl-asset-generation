"""Step B of PLAN.md: which rules v10 breaks, and are they followed consistently when alone? (user 2026-10-16: "check if
the rules that get broken in v10 are actually consistently followed in isolated runs"). Read-only on stored runs;
writes rule_breaks.json. Sends nothing.

Rule-alone decisions: for every rule wording, the luna rule-alone run whose text equals v10's (verify_isolation_coverage
.py): v10e1 for Buffer and engine status bits, v10u for Held outcomes (P1-HO) and the Phase 2 wording of Requests waiting
for a grant, v10fo for the 4 facts-first rules, v10r for the other 13 re-tested rules, v9 for the rest (old reply format
in every case). Two repeats each.

Measures (definitions fixed in PLAN.md before the v10 data; this script was written while v10 was running):
  M1 "barred alone, primary in the full prompt" exactly as analyze_isolation.analyze counts it (an element barred in both
     repeats of both wordings, or of the only wording; listed primary itself, or a field or record of it), for v10 and,
     on the same rule-alone decisions, for v9. Comparable with RULE_ISOLATION_RESULTS.md "Finding 4".
  M2 the staged test's measure: consistent bars of the Phase 2 wording (or of the only wording): an element barred in
     both repeats, itself or as a field of a barred record (not the other way round). A break = v10 lists that exact
     name primary in a run. Per wording: consistent-bar elements, broken (element, run) pairs, the break rate
     (pairs / (elements x 3)), modules, reference vs not, and the same count for v9.
  M3 bars unclear alone: elements barred in exactly one of the two repeats, and how often v10 lists them primary.
  M4 over-application in the full prompt: a reference element not primary in a v10 run whose excluding row (Phase 1 Not
     Kept, Phase 2 secondary or Not Reported) cites the rule (rule_consistency's keyword tags; a lower bound), while the
     rule alone does not bar it in both repeats ("not barred alone" when in neither, "unclear alone" when in one).
  M5 failure classes of v10's false positives and misses (element-runs), for v10 and v9: FP covered by a consistent bar
     (a broken rule), FP covered only by an unclear bar, FP no bar covers (missing rule or reference convention); misses
     by stage (rule_consistency / transitions.where_lost), and misses a consistent bar covers (the rule bars a reference
     element even alone).
Targets (PLAN.md): an M2 wording with at least 4 broken (element, run) pairs in at least 2 modules; at most 5, largest
  first; the others listed.
Self-tests (nothing is reported if one fails): analyze_isolation.selftest(); and the v9 rule-alone replies with v9's
  primaries reproduce the stored isolation_report.json M1 lists for every rule (the numbers behind Finding 4).

  python -B rule_breaks.py
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, ISOD, MODEL, EFFORT, V10, register  # noqa: E402

ISO = register()
sys.path.insert(0, str(LAB / "analysis" / "two_phase_v9__gpt-5.6-luna__high__r0-r2" / "consistency"))
import analyze_isolation as AN  # noqa: E402
import rule_consistency as RC  # noqa: E402

T, A, CV, CH, K = RC.T, RC.A, RC.CV, RC.CH, RC.K
V9 = "two_phase_v9"
REPS = (0, 1, 2)
RULES17 = ISO.RULES17
G3 = ISO.G3_RULES


def source(rid, ph):
    if rid == "P1-17":
        return "v10e1"
    if rid == "P1-HO" or (rid == "P1-26" and ph == "P2"):
        return "v10u"
    if rid in G3:
        return "v10fo"
    if rid in RULES17:
        return "v10r"
    return "v9"


def load_latest(mods):
    """{(rule, phase, module, rep): reply} with each wording from its source variant; problems if a source is short."""
    v9t = json.loads((ISOD / "rule_texts.json").read_text(encoding="utf-8"))
    want = [(rid, ph) for rid, t in v9t.items() if rid != "P1-22R" for ph in ("P1", "P2") if t.get(ph) and not (rid == "P1-26" and ph == "P2")]
    want += [("P1-HO", "P1"), ("P1-26", "P2")]
    R, probs = {}, []
    for rid, ph in want:
        v = source(rid, ph)
        ISO.use(v)
        for rep in (0, 1):
            got = 0
            for m in mods:
                f = ISO.run_root(rep=rep) / ph / rid / f"{m}.json"
                if not f.exists():
                    continue
                rec = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(rec.get("reply"), dict):
                    R[(rid, ph, m, rep)] = rec["reply"]
                    got += 1
            if got < len(mods) - 3:                       # v10r lost up to 3 replies of 82 per wording
                probs.append(f"{rid} {ph} rep {rep} ({v}): {got} of {len(mods)} modules")
    ISO.use("v9")
    return R, want, probs


def primaries(v, mods):
    lst = {}
    for r in REPS:
        for m in mods:
            f = CH.run_dir(v, MODEL, r, EFFORT) / "assets" / f"{m}.json"
            lst[(r, m)] = [x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]]
    prim = Counter()
    for (r, m), ns in lst.items():
        for n in set(ns):
            prim[(m, n)] += 1
    return lst, prim


def down(e, S):
    """e, or a record e is a field of, is in S (a bar of a record covers its fields, not the other way round)."""
    if e in S:
        return True
    parts = e.split(".")
    return any(".".join(parts[:i]) in S for i in range(1, len(parts)))


def selftests(mods, ref):
    ok = AN.selftest(log=lambda *a: None)
    print(f"self-test 1 (analyze_isolation.selftest): {'PASS' if ok else 'FAIL'}")
    stored = json.loads((ISOD / "isolation_report.json").read_text(encoding="utf-8"))
    ISO.use("v9")
    R9 = AN.load(lambda r: ISO.run_root(rep=r))
    _, prim9 = primaries(V9, mods)
    rep = AN.analyze(R9, prim9, ref)
    bad = [rid for rid, x in stored.items() if not rid.startswith("_") and rid in rep
           and x["barred alone, primary in the full prompt (element-runs)"] != rep[rid]["barred alone, primary in the full prompt (element-runs)"]]
    ok2 = not bad and len([k for k in stored if not k.startswith("_")]) == len([k for k in rep if not k.startswith("_")])
    print(f"self-test 2 (v9 rule-alone + v9 primaries reproduce isolation_report.json's lists for all "
          f"{len([k for k in stored if not k.startswith('_')])} rules): {'PASS' if ok2 else 'FAIL ' + str(bad[:5])}")
    return ok and ok2


def rules_for_v10():
    txt = (LAB / "prompts" / V10 / "phase1.md").read_text(encoding="utf-8")
    have = set(re.findall(r"^- ([A-Z][A-Za-z -]*?)(?: \([a-z]\))?\.", txt, re.M))
    out = {}
    for r, keys in A.RULE_KEYS.items():
        if r.split(" (")[0] in have:
            out[r] = list(keys) + (["relayed"] if r.startswith("Forwarded transactions") else [])
    out.update(RC.EXTRA)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, refl = CV.groups_and_ref()
    mods = groups["tuning"] + groups["held-out"]
    ref = {m: set(v) for m, v in refl.items()}
    if not selftests(mods, ref):
        sys.exit("a self-test failed: nothing reported")
    probs = CV.complete(V10, mods)
    if probs:
        sys.exit(f"v10 run not complete ({len(probs)} problems; first: {probs[0]})")
    R, want, lp = load_latest(mods)
    if lp:
        sys.exit("rule-alone sources incomplete: " + "; ".join(lp[:6]))
    titles = {rid: t["title"] for rid, t in json.loads((ISOD / "rule_texts.json").read_text(encoding="utf-8")).items()}
    titles["P1-HO"] = "Held outcomes, addresses and settings"
    lst10, prim10 = primaries(V10, mods)
    lst9, prim9 = primaries(V9, mods)
    split = {m: ("tuning_v2" if m not in groups["held-out: other 14"] else "heldout_v2") for m in mods}
    out = {"sources": {f"{rid} {ph}": source(rid, ph) for rid, ph in want}}
    # M1
    rep10, rep9 = AN.analyze(R, prim10, ref), AN.analyze(R, prim9, ref)
    out["M1"] = {rid: {"v10": rep10[rid]["interference element-runs on reference / not reference"],
                       "v9": rep9[rid]["interference element-runs on reference / not reference"],
                       "v10 cases": rep10[rid]["barred alone, primary in the full prompt (element-runs)"]}
                 for rid in rep10 if not rid.startswith("_")}
    out["candidate conflicts from the rule-alone runs (bar vs a clause that makes elements primary)"] = \
        rep10["_bar against a clause that makes elements primary (Phase 2, both repeats)"]
    # M2, M3
    m2, cbar, ubar = {}, defaultdict(set), defaultdict(set)
    for rid, ph in want:
        if ph == "P1" and (rid, "P2") in want:
            continue                                  # the Phase 2 wording decides labels
        rows = []
        keep_rule = AN.adds(rid) or rid in ("P1-HO", "P1-26")     # D10: a primary-making rule's decision list is "spared"
        for m in mods:
            if (rid, ph, m, 0) not in R or (rid, ph, m, 1) not in R:
                continue
            b = [AN.names(R[(rid, ph, m, r)], "spared" if keep_rule else "barred") for r in (0, 1)]
            cl = {n for (_, n) in CH.closed_names(m)}
            cons = {e for e in cl if down(e, b[0]) and down(e, b[1])}
            unc = {e for e in cl if down(e, b[0]) != down(e, b[1])}
            if not keep_rule:
                cbar[(rid, m)] |= cons
                ubar[(rid, m)] |= unc
            for e in sorted(cons):                      # a keep rule is "broken" in a run where its element is NOT primary
                hit = (lambda L: [r for r in REPS if (e in L[(r, m)]) != keep_rule])
                rows.append({"module": m, "element": e, "reference": e in ref[m], "split": split[m],
                             "v10 runs primary": hit(lst10), "v9 runs primary": hit(lst9)})
        br = [x for x in rows if x["v10 runs primary"]]
        un_rows = [(m, e) for (r_, m), es in ubar.items() if r_ == rid for e in es]
        m2[f"{rid} {ph}"] = {
            "title": titles.get(rid, rid), "kind": "keep (break = not primary)" if keep_rule else "bar", "consistent-bar elements": len(rows),
            "modules with a consistent bar": len({x["module"] for x in rows}),
            "v10 broken pairs": sum(len(x["v10 runs primary"]) for x in rows),
            "v10 broken pairs on reference elements": sum(len(x["v10 runs primary"]) for x in rows if x["reference"]),
            "v10 modules with a break": len({x["module"] for x in br}),
            "v10 break rate": round(sum(len(x["v10 runs primary"]) for x in rows) / (3 * len(rows)), 3) if rows else None,
            "v9 broken pairs": sum(len(x["v9 runs primary"]) for x in rows),
            "unclear-alone elements": len(un_rows),
            "unclear-alone elements primary in v10 (pairs)": sum(sum(e in lst10[(r, m)] for r in REPS) for m, e in un_rows),
            "broken": [f"{x['module'][8:]}:{x['element']} v10 {len(x['v10 runs primary'])}/3 v9 {len(x['v9 runs primary'])}/3"
                       + (" (reference)" if x["reference"] else "") for x in br]}
    out["M2"] = m2
    # M4 over-application (citations in v10's and v9's replies)
    rules10 = rules_for_v10()
    t2rid = {}
    for rid, t in titles.items():
        for r in rules10:
            if r.split(" (")[0] == t:
                t2rid[r] = rid
    m4 = {V10: Counter(), V9: Counter()}
    m4cases = defaultdict(list)
    for v, lst in ((V10, lst10), (V9, lst9)):
        rules = rules10 if v == V10 else RC.rules_for(v)
        for r in REPS:
            for m in mods:
                cit = RC.citations(v, r, m, rules)
                for n in ref[m]:
                    if n in lst[(r, m)]:
                        continue
                    for (e, rr, kind) in cit:
                        if e != n or kind == "P2 primary" or rr not in t2rid:
                            continue
                        rid = t2rid[rr]
                        state = "barred alone" if n in cbar.get((rid, m), set()) else \
                                "unclear alone" if n in ubar.get((rid, m), set()) else "not barred alone"
                        if state != "barred alone":
                            m4[v][(rid, state)] += 1
                            if v == V10:
                                m4cases[rid].append(f"{m[8:]}:{n} r{r} {kind} ({state})")
    out["M4"] = {v: {f"{rid} | {st}": c for (rid, st), c in sorted(m4[v].items())} for v in m4}
    out["M4 v10 cases"] = {rid: sorted(set(c)) for rid, c in m4cases.items()}
    # M5 failure classes
    allc = defaultdict(set)
    allu = defaultdict(set)
    for (rid, m), es in cbar.items():
        allc[m] |= es
    for (rid, m), es in ubar.items():
        allu[m] |= es
    m5 = {}
    for v, lst in ((V10, lst10), (V9, lst9)):
        c = Counter()
        for r in REPS:
            for m in mods:
                s = split[m]
                names = lst[(r, m)]
                for n in names:
                    if n in ref[m]:
                        continue
                    k = "FP: a consistent bar covers it (rule broken)" if n in allc[m] else \
                        "FP: only an unclear bar covers it" if n in allu[m] else "FP: no bar covers it"
                    c[(s, k)] += 1
                for n in ref[m]:
                    if n in names:
                        continue
                    st, _ = T.where_lost(v, r, m, n, names)
                    c[(s, f"miss at stage: {st}")] += 1
                    if n in allc[m]:
                        c[(s, "miss: a consistent bar covers this reference element")] += 1
        m5[v] = {f"{s} | {k}": n for (s, k), n in sorted(c.items())}
    out["M5"] = m5
    # targets
    elig = sorted(((k, x) for k, x in m2.items() if x["kind"] == "bar" and x["v10 broken pairs"] >= 4 and x["v10 modules with a break"] >= 2),
                  key=lambda kx: -kx[1]["v10 broken pairs"])
    out["targets"] = [k for k, _ in elig[:5]]
    out["eligible, not tested (cap of 5)"] = [k for k, _ in elig[5:]]
    (HERE / "rule_breaks.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nM2 (Phase 2 wording or only wording; consistent bars): wording | elements | v10 broken pairs (ref) | modules | rate | v9 pairs | unclear (v10 pairs)")
    for k, x in sorted(m2.items(), key=lambda kx: -kx[1]["v10 broken pairs"]):
        print(f"  {k:46s} {x['title'][:30]:30s} {x['consistent-bar elements']:4d} {x['v10 broken pairs']:4d} ({x['v10 broken pairs on reference elements']:2d}) "
              f"{x['v10 modules with a break']:3d} {x['v10 break rate'] if x['v10 break rate'] is not None else '-':>6} {x['v9 broken pairs']:4d} "
              f"{x['unclear-alone elements']:4d} ({x['unclear-alone elements primary in v10 (pairs)']})")
    print("\nM1 (as Finding 4: both wordings), element-runs [reference, not]: rule v10 | v9")
    for rid, x in out["M1"].items():
        if sum(x["v10"]) or sum(x["v9"]):
            print(f"  {rid:46s} {x['v10']} | {x['v9']}")
    print("\nM4 over-application (reference element dropped while citing the rule):", json.dumps(out["M4"], indent=1))
    print("\nM5 failure classes:", json.dumps(m5, indent=1))
    print("\ntargets:", out["targets"], "| eligible beyond the cap:", out["eligible, not tested (cap of 5)"])


if __name__ == "__main__":
    main()
