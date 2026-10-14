"""Analysis of the rule-isolation run (isolation.py). Read-only on the runs; writes isolation_report.json.

Per rule wording (rule x phase), over the modules with both repeats r0 and r1 stored:
  decision list  "barred" (for a clause that makes elements primary, ADDS_PRIMARIES: "spared", its kept list)
  flip           an element in the decision list of one repeat and not covered by the other repeat's decision list;
                 "covered" = the element itself, its record (any prefix before a ".") or one of its fields is listed:
                 listing a record or its fields is one decision
  contradiction  a flip whose element the other repeat lists on the opposite list (barred in one repeat, kept by the
                 rule's exception in the other): the same words read both ways for the same element
  disagreement   flips / elements decided in either repeat, per module; averaged over the modules the rule decides
                 something in (each module weighs the same, so one long enumeration does not dominate)
  unsure         modules with any "unsure" element; self-contradictions: an element both barred and kept in one reply
Per rule, Phase 1 wording against Phase 2 wording (same module): elements barred in both repeats of one wording and not
  covered by either repeat of the other (stable disagreements); of these, the ones the other wording keeps in both
  repeats (phase contradictions).
Rule against rule: an element a bar holds in both repeats and a clause that makes elements primary keeps in both
  repeats (same module, Phase 2). Another rule's "spared" list is not a verdict (it says the rule does not bar the
  element, not that the element is primary), so only those clauses can conflict with a bar.
Against the full prompt (v9 runs r0-r2): an element barred in both repeats of both wordings (or of its only wording)
  that v9 lists primary (itself or one of its fields), counted as element-runs; for an ADDS_PRIMARIES clause, an element
  it keeps in both repeats that no v9 run lists primary (counted as 3).

Readings set before the run (kept and reported as "pre-set flags"):
  "inconsistent alone"   pooled flip share >= 0.10 with 3+ flips, flips counted on the barred AND spared lists, names
                         exact
  "phase conflict"       3+ stable Phase 1 / Phase 2 disagreements
  "unclear"              "unsure" in 2+ modules for one wording, or 2+ elements both barred and kept in one reply
  "interference"         3+ element-runs barred alone but primary in the full prompt
Revision after seeing the data (2026-10-14, stated as such): the pre-set flip count flags 33 of 36 rules, because the
  "spared" list is a free enumeration (one reply lists 14 elements outside the rule, its repeat 3, with no decision
  changed) and a record is listed whole in one repeat and field by field in the other. The revised flags count flips on
  the decision list only, with record/field covering, and add contradictions:
  "contradicted alone"   contradictions in 2+ modules for one wording
  "unstable alone"       mean per-module disagreement >= 0.25 over 3+ modules (cut set before computing it)
  "phase contradiction"  2+ phase contradictions
A rule with "contradicted alone", "unstable alone", "phase conflict", "phase contradiction" or "unclear" goes to the
wording fix; one with only "interference" does not (its wording is followed when alone).
A (rule, phase, module) with one repeat missing (a failed call) is skipped and counted, never read as flips.
Self-test: a synthetic run folder with known flips, record/field listings, contradictions, spared-only differences,
unsure entries, a missing repeat, phase disagreements, interference and a clause conflict gives exactly the expected
counts.

  python analyze_isolation.py
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402

CH, K = ISO.CH, ISO.K


ADDS_PRIMARIES = ("P2X-decode-output-port", "P2X-unmixed-copy-output-port", "P2X-input-port-setting-the-value",
                  "P2X-side-by-side-port-signal", "P2X-rom-lookup-element")   # clauses that make elements primary


def adds(rid):
    return rid.startswith(ADDS_PRIMARIES)


def load(root_fn):
    """{(rule, phase, module, rep): reply} from every stored record (skips schema failures)."""
    out = {}
    for rep in (0, 1):
        base = root_fn(rep)
        if not base.exists():
            continue
        for f in base.glob("P*/*/*.json"):
            rec = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(rec.get("reply"), dict):
                out[(rec["rule"], rec["phase"], rec["module"], rec["rep"])] = rec["reply"]
    return out


def names(reply, key):
    return {x.get("element") for x in reply.get(key) or [] if isinstance(x, dict) and x.get("element")}


def covered(e, S):
    """e, its record (a prefix before a '.') or one of its fields is in S."""
    if e in S:
        return True
    parts = e.split(".")
    if any(".".join(parts[:i]) in S for i in range(1, len(parts))):
        return True
    return any(x.startswith(e + ".") for x in S)


def flips_of(D, O):
    """D, O: the decision list and the opposite list of the two repeats -> (flipped, contradicted) element sets."""
    f, c = set(), set()
    for a, b in ((0, 1), (1, 0)):
        for e in D[a]:
            if not covered(e, D[b]):
                f.add(e)
                if covered(e, O[b]):
                    c.add(e)
    return f, c


def analyze(R, primary_runs=None, ref=None):
    """R: {(rule, phase, module, rep): reply}; primary_runs: {(module, element): runs primary in v9} or None;
    ref: {module: reference element names} or None (marks stable decisions and interference on reference elements)."""
    ref = ref or {}
    prim_by_m = defaultdict(dict)
    for (m, n), c in (primary_runs or {}).items():
        prim_by_m[m][n] = c
    rules = sorted({k[0] for k in R})
    rep = {}
    for rid in rules:
        dkey, okey = ("spared", "barred") if adds(rid) else ("barred", "spared")
        row, st = {}, {}
        for ph in ("P1", "P2"):
            have = [{k[2] for k in R if k[0] == rid and k[1] == ph and k[3] == r} for r in (0, 1)]
            mods = sorted(have[0] & have[1])         # a module counts only with both repeats (a failed call is no flip)
            if not mods:
                continue
            pf = pt = 0
            flips = contras = decided = 0
            dis, fl_m, co_m, unsure_m, ex = [], 0, 0, 0, []
            stab_n, stab_ref = 0, []
            st[ph] = {}
            for m in mods:
                rp = [R[(rid, ph, m, r)] for r in (0, 1)]
                b = [names(x, "barred") for x in rp]
                k = [names(x, "spared") for x in rp]
                pf += len(b[0] ^ b[1]) + len(k[0] ^ k[1])                 # the pre-set count
                pt += len(b[0] | b[1]) + len(k[0] | k[1])
                D = [names(x, dkey) for x in rp]
                O = [names(x, okey) for x in rp]
                U = D[0] | D[1]
                f, c = flips_of(D, O)
                if U:
                    decided += 1
                    dis.append(len(f) / len(U))
                flips += len(f)
                contras += len(c)
                fl_m += bool(f)
                co_m += bool(c)
                ex += [f"{m}:{e}" for e in sorted(c)][:2]
                unsure_m += any(names(x, "unsure") for x in rp)
                st[ph][m] = ({e for e in D[0] if covered(e, D[1])}, U, {e for e in O[0] if covered(e, O[1])}, O[0] | O[1])
                stab_n += len(st[ph][m][0])
                stab_ref += [f"{m}:{e}" for e in sorted(st[ph][m][0]) if covered(e, ref.get(m, set()))]
            row[ph] = {"modules": len(mods), "modules missing a repeat (skipped)": len(have[0] ^ have[1]),
                       "modules deciding something": decided, "flips": flips, "contradictions": contras,
                       "modules with a flip": fl_m, "modules with a contradiction": co_m,
                       "mean disagreement per module": round(sum(dis) / len(dis), 3) if dis else 0.0,
                       "modules with unsure": unsure_m, "contradiction examples": ex[:8],
                       "stable decisions (both repeats)": stab_n, "stable decisions on reference elements": len(stab_ref),
                       "stable decisions on reference elements (examples)": stab_ref[:8],
                       "pre-set flips / decisions (barred and spared, exact names)": f"{pf}/{pt}",
                       "_pre-set share": pf / pt if pt else 0.0, "_pre-set flips": pf}
        dis, pco = [], []
        if "P1" in st and "P2" in st and not adds(rid):
            for m in sorted(set(st["P1"]) & set(st["P2"])):
                s1, any1, so1, _ = st["P1"][m]
                s2, any2, so2, _ = st["P2"][m]
                dis += [f"{m}:{e} (Phase 1 only)" for e in sorted(s1) if not covered(e, any2)]
                dis += [f"{m}:{e} (Phase 2 only)" for e in sorted(s2) if not covered(e, any1)]
                pco += [f"{m}:{e} (Phase 1 bars, Phase 2 keeps)" for e in sorted(s1) if not covered(e, any2) and covered(e, so2)]
                pco += [f"{m}:{e} (Phase 2 bars, Phase 1 keeps)" for e in sorted(s2) if not covered(e, any1) and covered(e, so1)]
        inter = []
        if primary_runs is not None:
            for m in sorted({k[2] for k in R if k[0] == rid}):
                prims = prim_by_m.get(m, {})
                if adds(rid):      # a clause that makes elements primary: kept alone in both repeats, never primary in v9
                    if m in st.get("P2", {}):
                        inter += [(m, e, 3, covered(e, ref.get(m, set()))) for e in sorted(st["P2"][m][0]) if not covered(e, set(prims))]
                    continue
                sets = [st[ph][m][0] for ph in ("P1", "P2") if ph in st and m in st[ph]]
                if not sets:
                    continue
                core = set.intersection(*sets)
                inter += [(m, p, c, p in ref.get(m, set())) for p, c in sorted(prims.items()) if covered(p, core)]
        selfc = sum(len(names(rp, "barred") & names(rp, "spared")) for (ra, pa, mm, rr), rp in R.items() if ra == rid)
        pre = {"inconsistent alone": any(r["_pre-set share"] >= 0.10 and r["_pre-set flips"] >= 3 for r in row.values()),
               "phase conflict": len(dis) >= 3,
               "unclear": any(r["modules with unsure"] >= 2 for r in row.values()) or selfc >= 2,
               "interference": sum(x[2] for x in inter) >= 3}
        f = {"contradicted alone": any(r["modules with a contradiction"] >= 2 for r in row.values()),
             "unstable alone": any(r["mean disagreement per module"] >= 0.25 and r["modules deciding something"] >= 3 for r in row.values()),
             "phase conflict": len(dis) >= 3, "phase contradiction": len(pco) >= 2,
             "unclear": pre["unclear"], "interference": pre["interference"]}
        for r in row.values():
            r.pop("_pre-set share")
            r.pop("_pre-set flips")
        rep[rid] = {**row, "Phase 1 / Phase 2 stable disagreements": dis, "phase contradictions": pco,
                    "elements both barred and kept in one reply": selfc,
                    "barred alone, primary in the full prompt (element-runs)": [f"{m}:{e} x{n}" + (" (reference)" if rf else " (not reference)" if ref else "")
                                                                                for m, e, n, rf in inter],
                    "interference element-runs on reference / not reference": [sum(x[2] for x in inter if x[3]), sum(x[2] for x in inter if not x[3])],
                    "pre-set flags": [k for k, v in pre.items() if v], "flags": [k for k, v in f.items() if v],
                    "goes to the wording fix": any(f[k] for k in ("contradicted alone", "unstable alone", "phase conflict",
                                                                  "phase contradiction", "unclear"))}
    # a bar against a clause that makes elements primary (Phase 2, both stable)
    conf = []
    stab = {}
    for (rid, ph, m, r) in R:
        if ph != "P2" or r != 0 or (rid, ph, m, 1) not in R:
            continue
        key = "spared" if adds(rid) else "barred"
        a, b = names(R[(rid, ph, m, 0)], key), names(R[(rid, ph, m, 1)], key)
        stab[(rid, m)] = {e for e in a if covered(e, b)}
    for (ra, m), sa in stab.items():
        if adds(ra):
            continue
        for (rb, mb), sb in stab.items():
            if mb == m and adds(rb):
                hit = sorted(e for e in sa if covered(e, sb))
                if hit:
                    conf.append({"bar": ra, "clause": rb, "module": m, "elements": hit})
    rep["_bar against a clause that makes elements primary (Phase 2, both repeats)"] = conf
    return rep


def selftest(log=print) -> bool:
    tmp = HERE / "_selftest_runs"
    shutil.rmtree(tmp, ignore_errors=True)

    def put(rid, ph, m, r, barred, spared=(), unsure=()):
        p = tmp / f"r{r}" / ph / rid / f"{m}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        it = lambda ns: [{"element": n} for n in ns]  # noqa: E731
        p.write_text(json.dumps({"rule": rid, "phase": ph, "module": m, "rep": r,
                                 "reply": {"barred": it(barred), "spared": it(spared), "unsure": it(unsure)}}), encoding="utf-8")
    # rule A, Phase 1, m1: x barred in r0 and kept in r1 (a contradiction); rec listed whole in r0 and by fields in r1 (no flip)
    put("A", "P1", "m1", 0, ["a", "b", "x", "rec"]); put("A", "P1", "m1", 1, ["a", "b", "rec.f1", "rec.f2"], spared=["x"], unsure=["u"])
    # m2: the same bar; the spared lists differ (no decision changed); w both barred and kept in one reply
    put("A", "P1", "m2", 0, ["w"], spared=["w", "s1", "s2", "s3"]); put("A", "P1", "m2", 1, ["w"], unsure=["v"])
    # m3: only r0 stored (a failed call): skipped
    put("A", "P1", "m3", 0, ["q", "r"])
    # Phase 2 wording, m1: bars a, b, c stably and keeps rec stably -> rec: Phase 1 only and a phase contradiction; c: Phase 2 only
    put("A", "P2", "m1", 0, ["a", "b", "c"], spared=["rec"]); put("A", "P2", "m1", 1, ["a", "b", "c"], spared=["rec"])
    # a clause that makes elements primary, m1: keeps p and c in both repeats; q kept in r0, barred in r1 (a contradiction)
    cl = "P2X-input-port-setting-the-value"
    put(cl, "P2", "m1", 0, [], spared=["p", "q", "c"]); put(cl, "P2", "m1", 1, ["q"], spared=["p", "c"])
    # a non-clause rule keeping a in P1 is not a conflict
    put("B", "P1", "m1", 0, [], spared=["a"]); put("B", "P1", "m1", 1, [])
    R = load(lambda r: tmp / f"r{r}")
    rep = analyze(R, primary_runs={("m1", "a"): 2, ("m1", "rec.f1"): 1, ("m1", "p"): 3}, ref={"m1": {"a", "rec.f2", "c"}})
    shutil.rmtree(tmp, ignore_errors=True)
    a, p1 = rep["A"], rep["A"]["P1"]
    c = rep[cl]["P2"]
    checks = {
        "P1 flips 1 (x), record/field listing no flip": p1["flips"] == 1,
        "P1 contradiction 1 in 1 module": p1["contradictions"] == 1 and p1["modules with a contradiction"] == 1,
        "P1 disagreement mean (1/6 + 0) / 2": abs(p1["mean disagreement per module"] - round((1 / 6) / 2, 3)) < 1e-9,
        "missing repeat skipped": p1["modules"] == 2 and p1["modules missing a repeat (skipped)"] == 1,
        "unsure in 2 modules": p1["modules with unsure"] == 2,
        "pre-set count includes spared-only differences": p1["pre-set flips / decisions (barred and spared, exact names)"] == "9/12",
        "self-contradiction 1": a["elements both barred and kept in one reply"] == 1,
        "phase disagreements": a["Phase 1 / Phase 2 stable disagreements"] == ["m1:rec (Phase 1 only)", "m1:c (Phase 2 only)"],
        "phase contradiction": a["phase contradictions"] == ["m1:rec (Phase 1 bars, Phase 2 keeps)"],
        "interference: a primary (x2), rec.f1 not (rec is not barred by P2)": a["barred alone, primary in the full prompt (element-runs)"] == ["m1:a x2 (reference)"],
        "stable decisions on reference elements: P1 a and rec (covers rec.f2); P2 a and c": p1["stable decisions on reference elements"] == 2
            and a["P2"]["stable decisions on reference elements"] == 2 and p1["stable decisions (both repeats)"] == 4,
        "clause flips on its kept list": c["flips"] == 1 and c["contradictions"] == 1,
        "clause interference: c kept, never primary": rep[cl]["barred alone, primary in the full prompt (element-runs)"] == ["m1:c x3 (reference)"],
        "bar vs clause conflict: c only": rep["_bar against a clause that makes elements primary (Phase 2, both repeats)"]
            == [{"bar": "A", "clause": cl, "module": "m1", "elements": ["c"]}],
        "flags": a["flags"] == ["unclear"] and "inconsistent alone" in a["pre-set flags"],
    }
    bad = [k for k, v in checks.items() if not v]
    log(f"analysis self-test ({len(checks)} checks on a synthetic run): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    if bad:
        log(json.dumps(rep, indent=1)[:3000])
    return not bad


def examples(rid, ph, cases, n=4):
    """For contradiction examples 'module:element': each repeat's list, rule words and why."""
    out = []
    for case in cases[:n]:
        m, e = case.split(":", 1)
        two = []
        for r in (0, 1):
            rec = json.loads(ISO.path(rid, ph, m, r).read_text(encoding="utf-8"))["reply"]
            hit = [(k, x) for k in ("barred", "spared", "unsure") for x in rec.get(k) or []
                   if isinstance(x, dict) and x.get("element") and covered(e, {x["element"]})]
            two.append([{"repeat": r, "list": k, "element": x["element"], "rule words": x.get("rule words"), "why": x.get("why")}
                        for k, x in hit[:2]])
        out.append({"case": case, "repeats": two})
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if not selftest():
        sys.exit(1)
    R = load(lambda r: ISO.run_root(rep=r))
    if not R:
        print("no isolation replies stored yet")
        return
    prim = Counter()
    for m in K.gt_modules()["tuning"] + K.gt_modules()["heldout"]:
        for r in (0, 1, 2):
            f = CH.run_dir(ISO.V9, "gpt-5.6-luna", r, "high") / "assets" / f"{m}.json"
            for n in {x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]}:
                prim[(m, n)] += 1
    sys.path.insert(0, str(HERE.parent / "heldout_versions__gpt-5.6-luna__high__r0-r2"))
    import compare_versions as CV
    _, refl = CV.groups_and_ref()
    rep = analyze(R, prim, {m: set(v) for m, v in refl.items()})
    for rid, x in rep.items():
        if not rid.startswith("_"):
            for ph in ("P1", "P2"):
                if ph in x:
                    x[ph]["contradiction details"] = examples(rid, ph, x[ph]["contradiction examples"])
    (HERE / "isolation_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    texts = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    print(f"replies read: {len(R)}")
    print(f"{'rule':44s} {'title':30s} ph mods dec flips contra(mods) mean-dis unsure stable(ref) | P1/P2 dis contra | interf ref/not | flags")
    for rid, x in rep.items():
        if rid.startswith("_"):
            continue
        for ph in ("P1", "P2"):
            if ph not in x:
                continue
            r = x[ph]
            print(f"{rid:44s} {texts.get(rid, {}).get('title', '')[:30]:30s} {ph} {r['modules']:4d} {r['modules deciding something']:3d} "
                  f"{r['flips']:5d} {r['contradictions']:4d}({r['modules with a contradiction']:2d}) {r['mean disagreement per module']:8.3f} "
                  f"{r['modules with unsure']:6d} {r['stable decisions (both repeats)']:4d}({r['stable decisions on reference elements']:3d}) | "
                  f"{len(x['Phase 1 / Phase 2 stable disagreements']):4d} {len(x['phase contradictions']):3d} | "
                  f"{x['interference element-runs on reference / not reference']} | {x['flags']}")
    fix = [rid for rid, x in rep.items() if not rid.startswith("_") and x["goes to the wording fix"]]
    pre = [rid for rid, x in rep.items() if not rid.startswith("_") and "inconsistent alone" in x["pre-set flags"]]
    print(f"\nto the wording fix (revised flags): {len(fix)} of {len([k for k in rep if not k.startswith('_')])}; "
          f"pre-set 'inconsistent alone' alone would flag {len(pre)}")
    conf = rep["_bar against a clause that makes elements primary (Phase 2, both repeats)"]
    print(f"bar against a primary-making clause: {len(conf)} (bar, clause, module) cases, "
          f"{sum(len(c['elements']) for c in conf)} elements; by pair:",
          dict(Counter((c["bar"], c["clause"][:30]) for c in conf).most_common(10)))


if __name__ == "__main__":
    main()
