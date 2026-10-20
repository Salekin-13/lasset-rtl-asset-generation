"""Ambiguity of each prompt rule, and how it changed with the tunings (user 2026-10-15: "will continuously tuning with
increasingly narrowed cases cause the prompt to be overtuned ...? do a thorough analysis on the ambiguity of each prompt
rule and evaluate how it changed with the tunings done"). Code only, read-only on the stored isolation runs and prompt
files; writes ambiguity_by_rule.json. No model calls.

A. Measured ambiguity per rule wording (rule x phase), in each isolation test that ran it (v9: 59 wordings; v10r: 17
   rules; v10f: 4; v10f2: 2; v10f3: 1). Same 41 modules, 2 identical repeats each.
   disagreement rate  signals one run bars and the other does not / signals either run bars, summed over the modules
                      (a record and its fields count as one: analyze_isolation.flips_of). Reads only the barred list
                      (for a clause that makes signals primary: its kept list), so it is comparable across all tests.
   modules split      modules where the two runs' decision lists differ, of the modules where either run decides
   opposite answers   one run bars, the other keeps (contradictions); not comparable for v10f2 / v10f3, whose format
                      allows "an exception applies" only for a part labelled Exceptions
   two readings       opposite answers whose runs quote different clauses (clause_check); v9 and v10r only
   applied once       modules where one run decided something and the other nothing
   P1/P2              signals one wording bars in both runs and the other wording in neither run (analyze_isolation)
   breadth            modules where the wording bars (or keeps, for a clause that makes signals primary) something in
                      both runs
B. Text of each v9 wording: words, clauses (clause_check.clauses), exception markers, limiters; Spearman rank
   correlation with the disagreement rate over the v9 wordings that decide something in 3+ modules (cut chosen here).
   Clause use: per clause, modules where a stable decision (both runs, either list) quotes it (clause_check.best_clause
   on the reply's "rule words"); clauses quoted in no module and in exactly one module.
C. Each Phase 1 rule's text over the prompt versions v2 ... v9 (the "- Title." bullet of phase1.md): words, exception
   markers. A rule absent from a version is None.
D. Do the fixes help beyond the cases they were made from? Per transition (v9 -> v10r, v10r -> v10f, v10f -> v10f2,
   v10f2 -> v10f3) and per wording, the old test splits the modules into "problem" (the two runs' decision lists
   differ) and "clean" (they agree, empty included). With no real change, regression to the mean alone makes problem
   modules improve and clean ones worsen. Under a no-change model where module m has instability q_m:
     P(new split | old clean) = E[q(1-q)]/E[1-q] <= E[q] <= E[q^2]/E[q] = P(new split | old problem),
   with E[q] estimated by the wording's old share of split modules (base rate). So clean modules turning split ABOVE the
   base rate = trouble the change caused beyond noise; problem modules staying split BELOW the base rate = a fix beyond
   noise. Binomial tails (Hoeffding 1956: a sum of unequal Bernoullis is no wider than the binomial with the same mean,
   for counts at least one above the mean) give rough one-sided p-values. Totals over all 41 modules (no selection)
   are also given. Each transition changes the rule text and, for v9 -> v10r and v10r -> v10f, the shared context and
   reply format as well.

Self-test (nothing is reported if it fails):
  - v9 per wording: flips, contradictions, modules with a flip, stable decisions and P1/P2 stable disagreements equal
    isolation_report.json; two readings / format equal clause_contradictions.json;
  - v10r, v10f, v10f2, v10f3: flips, stable, applied once and P1/P2 equal compare_v10r.json / compare_v10f*.json;
  - text features on a hand-counted sentence; the v9 "- Slices." bullet hand-checked (first and last words).

  python -B ambiguity_by_rule.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import binom, spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402
import clause_check as CC  # noqa: E402

LAB = HERE.parents[1]
VARIANTS = ["v9", "v10r", "v10f", "v10f2", "v10f3"]
TRANSITIONS = [("v9", "v10r"), ("v10r", "v10f"), ("v10f", "v10f2"), ("v10f2", "v10f3")]
VERSIONS = ["v2", "v4a", "v5", "v5f", "v6", "v6d", "v7", "v8", "v9"]
EXC = re.compile(r"\b(unless|except|apart from|other than|not covered|judged as usual|leaving out|excluding|but)\b", re.I)
LIM = re.compile(r"\b(only|every|never|any|each|all)\b", re.I)


def text_features(t):
    t = t or ""
    return {"words": len(t.split()), "clauses": len(CC.clauses(t)) if t else 0, "exception markers": len(EXC.findall(t)),
            "limiters": len(LIM.findall(t)), "brackets": t.count("(")}


def per_wording(R, rid, ph):
    """Module-level sets for one wording: {module: (flips, contradictions, union, stable, D0, D1)}."""
    dkey, okey = ("spared", "barred") if A.adds(rid) else ("barred", "spared")
    have = [{k[2] for k in R if k[0] == rid and k[1] == ph and k[3] == r} for r in (0, 1)]
    out = {}
    for m in sorted(have[0] & have[1]):
        rp = [R[(rid, ph, m, r)] for r in (0, 1)]
        D = [A.names(x, dkey) for x in rp]
        O = [A.names(x, okey) for x in rp]
        f, c = A.flips_of(D, O)
        out[m] = {"flips": f, "contra": c, "union": D[0] | D[1], "stable": {e for e in D[0] if A.covered(e, D[1])},
                  "D": D, "O": O}
    return out


def measure(R, texts, rep, rid, ph):
    W = per_wording(R, rid, ph)
    fl = sum(len(w["flips"]) for w in W.values())
    un = sum(len(w["union"]) for w in W.values())
    deciding = [m for m, w in W.items() if w["union"]]
    split = [m for m, w in W.items() if w["flips"]]
    once = sum(1 for w in W.values() if bool(w["D"][0]) != bool(w["D"][1]))
    two = fmt = 0
    if texts and rid in texts and texts[rid].get(ph):
        for m, e in CC.contradictions(R, rid, ph):
            k = CC.classify(R, texts, rid, ph, m, e)[0]
            two += k == "different clauses"
            fmt += k == "same clause"
    x = rep[rid][ph]
    return {"modules": len(W), "deciding": len(deciding), "split modules": len(split),
            "flips": fl, "decided (union)": un, "disagreement rate": round(fl / un, 3) if un else None,
            "opposite answers": sum(len(w["contra"]) for w in W.values()), "two readings": two, "format": fmt,
            "applied once": once, "unsure modules": x["modules with unsure"],
            "stable": sum(len(w["stable"]) for w in W.values()),
            "breadth": sum(1 for w in W.values() if w["stable"]),
            "_split": split, "_W": W}


def load(variant):
    ISO.use(variant)
    R = A.load(lambda r: ISO.run_root(rep=r))
    tf = ISO.texts_file()
    texts = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else {}
    ISO.use("v9")
    return R, texts


def clause_use(R, texts, rid, ph, W):
    """Per clause of the wording: modules where a stable decision (both runs, either list) quotes it."""
    cl = CC.clauses(texts[rid][ph])
    used = defaultdict(set)
    for m in W:
        rp = [R[(rid, ph, m, r)] for r in (0, 1)]
        for key in ("barred", "spared"):
            s = {e for e in A.names(rp[0], key) if A.covered(e, A.names(rp[1], key))}
            for e in s:
                idx = {CC.best_clause(" ".join(CC.cited(rp[r], key, e)), cl) for r in (0, 1)}
                for i in idx - {None}:
                    used[i].add(m)
    n = Counter(len(used.get(i, ())) for i in range(len(cl)))
    return {"clauses": len(cl), "quoted in no module": n[0], "quoted in exactly one module": n[1],
            "one-module clauses": [{"clause": cl[i][:160], "module": sorted(used[i])[0]} for i in range(len(cl)) if len(used.get(i, ())) == 1],
            "_used": {cl[i]: sorted(used.get(i, ())) for i in range(len(cl))}}


def decision_clause(c):
    """A clause that states a decision, not a heading ("- Slices."), a list lead-in ("Judged as usual:") or a stub."""
    return len(c.split()) >= 4 and not c.rstrip().endswith(":") and not c.startswith("- ")


def bullets(version):
    p = LAB / "prompts" / f"two_phase_{version}" / "phase1.md"
    out = {}
    for line in p.read_text(encoding="utf-8").split("\n"):
        mm = re.match(r"^- ([A-Z][A-Za-z ,/\-]*)\.\s", line)
        if mm:
            out[mm.group(1).strip()] = line
    return out


def selftest(meas, reps):
    bad = []
    iso = json.loads((HERE / "isolation_report.json").read_text(encoding="utf-8"))
    cc = json.loads((HERE / "clause_contradictions.json").read_text(encoding="utf-8"))
    for rid, row in meas["v9"].items():
        for ph, x in row.items():
            if ph not in ("P1", "P2"):
                continue
            b = iso[rid][ph]
            if (x["flips"], x["opposite answers"], x["split modules"], x["stable"]) != (
                    b["flips"], b["contradictions"], b["modules with a flip"], b["stable decisions (both repeats)"]):
                bad.append(f"v9 {rid} {ph} vs isolation_report")
            c = cc.get(f"{rid} {ph}")
            if c and (x["two readings"], x["format"]) != (c["different clauses"], c["same clause"]):
                bad.append(f"v9 {rid} {ph} clause classes")
        if row["P1/P2"] != len(iso[rid]["Phase 1 / Phase 2 stable disagreements"]):
            bad.append(f"v9 {rid} P1/P2")
    for new, fname, old in (("v10r", "compare_v10r.json", None), ("v10f", "compare_v10f.json", None),
                            ("v10f2", "compare_v10f2.json", None), ("v10f3", "compare_v10f3.json", None)):
        ref = json.loads((HERE / fname).read_text(encoding="utf-8"))[new]
        for rid, row in ref.items():
            for ph in ("P1", "P2"):
                if ph not in row:
                    continue
                x = meas[new][rid][ph]
                if (x["flips"], x["stable"], x["applied once"]) != (row[ph]["flips"], row[ph]["stable"], row[ph]["applied once"]):
                    bad.append(f"{new} {rid} {ph} vs {fname}")
            if meas[new][rid]["P1/P2"] != row["P1/P2 stable disagreements"]:
                bad.append(f"{new} {rid} P1/P2 vs {fname}")
    # text features, hand-counted: 13 words, "unless" + "apart from" = 2 exception markers, "only" x2 + "every" = 3
    tf = text_features("Only this, apart from that, unless it holds; every line only (here) counts.")
    if (tf["words"], tf["exception markers"], tf["limiters"], tf["brackets"]) != (13, 2, 3, 1):
        bad.append(f"text_features {tf}")
    s = bullets("v9").get("Slices", "")
    if not (s.startswith("- Slices. A signal (not a port) whose only assignment") and len(s.split()) > 40):
        bad.append("v9 Slices bullet")
    return bad


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    _, refl = __import__("compare_v10r").CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    meas, data = {}, {}
    for v in VARIANTS:
        R, texts = load(v)
        rep = A.analyze(R, None, ref)
        data[v] = (R, texts)
        meas[v] = {}
        for rid in sorted({k[0] for k in R}):
            row = {ph: measure(R, texts if v in ("v9", "v10r") else None, rep, rid, ph) for ph in ("P1", "P2") if ph in rep[rid]}
            row["P1/P2"] = len(rep[rid]["Phase 1 / Phase 2 stable disagreements"])
            row["_P1/P2 list"] = rep[rid]["Phase 1 / Phase 2 stable disagreements"]
            meas[v][rid] = row
    bad = selftest(meas, None)
    print("self-test (reproduces isolation_report, clause_contradictions, compare_v10r/v10f/v10f2/v10f3; text features):",
          "PASS" if not bad else f"FAIL {bad}")
    if bad:
        sys.exit(1)
    texts9 = data["v9"][1]
    titles = {rid: texts9[rid]["title"] for rid in texts9}

    # ---- A: per wording, every test
    A_out = {}
    for rid in sorted(meas["v9"]):
        A_out[rid] = {"title": titles.get(rid, rid)}
        for v in VARIANTS:
            if rid in meas[v]:
                A_out[rid][v] = {ph: {k: x for k, x in meas[v][rid][ph].items() if not k.startswith("_")}
                                 for ph in ("P1", "P2") if ph in meas[v][rid]}
                A_out[rid][v]["P1/P2"] = meas[v][rid]["P1/P2"]
    print("\nA. disagreement rate (signals one run bars and the other not / signals either run bars), split modules / deciding, P1/P2")
    print(f"{'rule':24s} {'title':30s} " + " | ".join(f"{v:>22s}" for v in VARIANTS))
    for rid in sorted(meas["v9"], key=lambda r: -max((meas["v9"][r][p]["disagreement rate"] or 0) for p in ("P1", "P2") if p in meas["v9"][r])):
        cells = []
        for v in VARIANTS:
            if rid not in meas[v]:
                cells.append(f"{'':>22s}")
                continue
            s = []
            for ph in ("P1", "P2"):
                if ph in meas[v][rid]:
                    x = meas[v][rid][ph]
                    s.append(f"{x['disagreement rate'] if x['disagreement rate'] is not None else '-'}({x['split modules']}/{x['deciding']})")
            cells.append(f"{' '.join(s) + ' ' + str(meas[v][rid]['P1/P2']):>22s}")
        print(f"{rid:24s} {titles.get(rid, rid)[:30]:30s} " + " | ".join(cells))

    # ---- B: text features vs disagreement (v9) and clause use
    rows = []
    B_out = {}
    for rid, row in meas["v9"].items():
        for ph in ("P1", "P2"):
            if ph not in row:
                continue
            x = row[ph]
            tf = text_features(texts9[rid][ph])
            cu = clause_use(data["v9"][0], texts9, rid, ph, x["_W"])
            B_out[f"{rid} {ph}"] = {"title": titles[rid], **tf, "disagreement rate": x["disagreement rate"],
                                    "two readings": x["two readings"], "deciding": x["deciding"], "clause use": cu}
            if x["deciding"] >= 3 and x["disagreement rate"] is not None:
                rows.append((x["disagreement rate"], x["two readings"] / max(x["deciding"], 1), tf))
    corr = {}
    for k in ("words", "clauses", "exception markers", "limiters", "brackets"):
        r1 = spearmanr([r[0] for r in rows], [r[2][k] for r in rows])
        r2 = spearmanr([r[1] for r in rows], [r[2][k] for r in rows])
        corr[k] = {"vs disagreement rate": [round(float(r1.statistic), 3), round(float(r1.pvalue), 4)],
                   "vs two readings per deciding module": [round(float(r2.statistic), 3), round(float(r2.pvalue), 4)]}
    print(f"\nB. Spearman over {len(rows)} v9 wordings deciding something in 3+ modules: [rho, p]")
    for k, v in corr.items():
        print(f"  {k:18s} {v}")
    tot = Counter()
    for k, b in B_out.items():
        tot["clauses"] += b["clause use"]["clauses"]
        tot["no module"] += b["clause use"]["quoted in no module"]
        tot["one module"] += b["clause use"]["quoted in exactly one module"]
    print(f"  clause use over all v9 wordings: {tot['clauses']} clauses; quoted in no module {tot['no module']}, "
          f"in exactly one module {tot['one module']}")
    # B2: decision clauses quoted in exactly one module - which module group? (original split: 15 tuning modules, on
    # whose replies the v5-v8 rules were written; 26 held-out). Baseline: every module use of the decision clauses
    # quoted in 2+ modules.
    groups, _ = __import__("compare_v10r").CV.groups_and_ref()
    tun15 = set(groups["tuning"])
    one, multi = Counter(), Counter()
    dec = Counter()
    pairs = set()                                    # (rule, module): a clause in both wordings counts once
    for k, b in B_out.items():
        for c, mods in b["clause use"].pop("_used").items():
            if not decision_clause(c):
                continue
            dec["decision clauses"] += 1
            dec["quoted in no module"] += not mods
            if len(mods) == 1:
                one["tuning 15" if mods[0] in tun15 else "held-out 26"] += 1
                pairs.add((k.split()[0], mods[0]))
            elif len(mods) >= 2:
                for m in mods:
                    multi["tuning 15" if m in tun15 else "held-out 26"] += 1
    B2 = {"decision clauses": dec["decision clauses"], "quoted in no module": dec["quoted in no module"],
          "quoted in exactly one module, by that module's group": dict(one),
          "module uses of clauses quoted in 2+ modules, by group (baseline)": dict(multi),
          "tuning modules / all modules": f"{len(tun15)}/41"}
    base = multi["tuning 15"] / max(sum(multi.values()), 1)
    pt = sum(1 for _, m in pairs if m in tun15)
    B2["(rule, module) pairs of one-module clauses: tuning 15 / all"] = f"{pt}/{len(pairs)}"
    B2["p (pairs in tuning modules, binomial against the baseline share)"] = round(float(binom.sf(pt - 1, len(pairs), base)), 5)
    B2["baseline share in tuning modules"] = round(base, 3)
    print("  B2 decision clauses (no headings or lead-ins):", B2)

    # ---- C: Phase 1 text over versions
    C_out = {}
    bl = {v: bullets(v) for v in VERSIONS}
    for rid in sorted(meas["v9"]):
        t = titles.get(rid, "")
        if not rid.startswith("P1-") or rid.endswith("R"):
            continue
        C_out[rid] = {"title": t, **{v: ({"words": len(bl[v][t].split()), "exception markers": len(EXC.findall(bl[v][t]))}
                                         if t in bl[v] else None) for v in VERSIONS}}
    print("\nC. Phase 1 bullet words (exception markers) per version")
    print(f"{'rule':6s} {'title':30s} " + " ".join(f"{v:>9s}" for v in VERSIONS))
    for rid, r in C_out.items():
        print(f"{rid:6s} {r['title'][:30]:30s} " + " ".join(f"{(str(r[v]['words']) + '(' + str(r[v]['exception markers']) + ')') if r[v] else '-':>9s}" for v in VERSIONS))
    allw = {v: sum(len(x.split()) for x in bl[v].values()) for v in VERSIONS}
    print("  all Phase 1 bullets, words:", allw)

    # ---- D: generalization of the fixes
    D_out = {}
    tv2 = set(json.loads((LAB / "splits" / "tuning_v2.json").read_text(encoding="utf-8"))["tuning"])
    tv2 = {m if m.startswith("neorv32_") else "neorv32_" + m for m in tv2}
    print("\nD. problem modules (old runs split) vs clean modules (old runs agree), per transition, summed over wordings")
    for old, new in TRANSITIONS:
        agg = Counter()
        per = {}
        newly = []
        for rid in sorted(meas[new]):
            if rid not in meas[old]:
                continue
            for ph in ("P1", "P2"):
                if ph not in meas[old][rid] or ph not in meas[new][rid]:
                    continue
                o, n = meas[old][rid][ph], meas[new][rid][ph]
                mods = sorted(set(o["_W"]) & set(n["_W"]))
                so, sn = set(o["_split"]), set(n["_split"])
                p = len(so & set(mods)) / len(mods) if mods else 0.0
                prob = [m for m in mods if m in so]
                clean = [m for m in mods if m not in so]
                kp = sum(1 for m in prob if m in sn)
                kc = sum(1 for m in clean if m in sn)
                per[f"{rid} {ph}"] = {"modules": len(mods), "base rate": round(p, 3), "problem": len(prob),
                                      "problem still split": kp, "clean": len(clean), "clean now split": kc,
                                      "flips old -> new (all modules)": f"{o['flips']} -> {n['flips']}",
                                      "rate old -> new": f"{o['disagreement rate']} -> {n['disagreement rate']}"}
                agg["problem"] += len(prob)
                agg["problem in heldout_v2"] += sum(1 for m in prob if m not in tv2)
                agg["kp"] += kp
                agg["clean"] += len(clean)
                agg["kc"] += kc
                agg["bound_p"] += len(prob) * p
                agg["bound_c"] += len(clean) * p
                agg["flips_old"] += o["flips"]
                agg["flips_new"] += n["flips"]
                agg["union_old"] += o["decided (union)"]
                agg["union_new"] += n["decided (union)"]
                agg["split_old"] += len(so & set(mods))
                agg["split_new"] += len(sn & set(mods))
                agg["mods"] += len(mods)
                for m in clean:
                    if m in sn:
                        ex = sorted(n["_W"][m]["flips"])[:3]
                        newly.append(f"{rid} {ph} {m}: {', '.join(ex)}")
        # one-sided tails (rough; see the docstring)
        pc = (binom.sf(agg["kc"] - 1, agg["clean"], agg["bound_c"] / agg["clean"]) if agg["clean"] and agg["kc"] else 1.0)
        pp = (binom.cdf(agg["kp"], agg["problem"], agg["bound_p"] / agg["problem"]) if agg["problem"] else 1.0)
        D_out[f"{old} -> {new}"] = {
            "wordings": len(per), "module-wordings": agg["mods"],
            "all modules: split module-wordings old -> new": f"{agg['split_old']} -> {agg['split_new']}",
            "all modules: flips old -> new": f"{agg['flips_old']} -> {agg['flips_new']}",
            "all modules: disagreement rate old -> new": f"{round(agg['flips_old'] / agg['union_old'], 3) if agg['union_old'] else None} -> "
                                                         f"{round(agg['flips_new'] / agg['union_new'], 3) if agg['union_new'] else None}",
            "problem modules still split": f"{agg['kp']} of {agg['problem']} (no-change floor {agg['bound_p']:.1f})",
            "p (problem side, fewer than noise allows)": round(float(pp), 4),
            "clean modules now split": f"{agg['kc']} of {agg['clean']} (no-change ceiling {agg['bound_c']:.1f})",
            "p (clean side, more than noise allows)": round(float(pc), 4),
            "problem module-wordings in heldout_v2 (the 14 kept for 'does not hurt' checks)": f"{agg['problem in heldout_v2']} of {agg['problem']}",
            "clean modules now split (examples)": newly, "per wording": per}
        d = D_out[f"{old} -> {new}"]
        print(f"  {old} -> {new}: wordings {len(per)}; all modules: split {d['all modules: split module-wordings old -> new']}, "
              f"rate {d['all modules: disagreement rate old -> new']}; problem still split {d['problem modules still split']} "
              f"p={d['p (problem side, fewer than noise allows)']}; clean now split {d['clean modules now split']} "
              f"p={d['p (clean side, more than noise allows)']}; problem module-wordings in heldout_v2 "
              f"{d['problem module-wordings in heldout_v2 (the 14 kept for ' + chr(39) + 'does not hurt' + chr(39) + ' checks)']}")
    out = {"A per wording and test": A_out, "B text vs disagreement (v9)": {"correlations": corr, "per wording": B_out,
                                                                          "clause use totals": dict(tot), "B2": B2},
           "C Phase 1 text over versions": {"per rule": C_out, "all bullets words": allw},
           "D fixes beyond their cases": D_out}
    (HERE / "ambiguity_by_rule.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=sorted), encoding="utf-8")
    print("\nwritten ambiguity_by_rule.json")



def table():
    """Markdown rows per rule from ambiguity_by_rule.json (run main() first): v9 and latest test, where the v9 / v10r
    two readings sit (clause_contradictions*.json, top group by elements). Verdict cuts (chosen here, stated in the
    report): too few = fewer than 3 deciding modules in every wording; clear = every wording with 3+ deciding modules
    has rate < 0.15, two readings <= 1 and P1/P2 <= 2."""
    sys.stdout.reconfigure(encoding="utf-8")
    d = json.loads((HERE / "ambiguity_by_rule.json").read_text(encoding="utf-8"))["A per wording and test"]
    cc = {"v9": json.loads((HERE / "clause_contradictions.json").read_text(encoding="utf-8")),
          "v10r": json.loads((HERE / "clause_contradictions_v10r.json").read_text(encoding="utf-8"))}

    def cell(x):
        if x is None:
            return "–"
        r = x["disagreement rate"]
        return f"{'–' if r is None else f'{r:.2f}'} ({x['split modules']}/{x['deciding']})"

    def verdict(row):
        ws = [row[p] for p in ("P1", "P2") if p in row]
        if all(w["deciding"] < 3 for w in ws):
            return "too few cases"
        ok = all((w["disagreement rate"] or 0) < 0.15 and w["two readings"] <= 1 for w in ws if w["deciding"] >= 3)
        return "clear" if ok and row["P1/P2"] <= 2 else "ambiguous"

    def where(v, rid):
        g = []
        for ph in ("P1", "P2"):
            x = cc[v].get(f"{rid} {ph}")
            grp = (x or {}).get("reading-difference groups") if isinstance(x, dict) else x   # v10r file: a list
            if grp:
                t = max(grp, key=lambda z: z.get("elements", z.get("n", 0)))
                kept = t.get("kept by clause", t.get("keep", ""))
                g.append(f"{ph}: bar vs \"{kept[:70]}\" ({t.get('elements', t.get('n'))}, e.g. {t['examples'][0].replace('neorv32_', '')})")
        return "; ".join(g)

    order = ["v10f3", "v10f2", "v10f", "v10r"]
    print("| Rule | v9 P1 | v9 P2 | v9 two readings | v9 P1/P2 | v9 verdict | latest test | latest P1 | latest P2 | latest P1/P2 | where v9 read two ways |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for rid, row in sorted(d.items(), key=lambda kv: kv[0]):
        v9 = row["v9"]
        two = sum(v9[p]["two readings"] for p in ("P1", "P2") if p in v9)
        last = next((v for v in order if v in row), None)
        lr = row.get(last) if last else None
        print(f"| {rid} {row['title']} | {cell(v9.get('P1'))} | {cell(v9.get('P2'))} | {two} | {v9['P1/P2']} | {verdict(v9)} | "
              f"{last or '–'} | {cell(lr.get('P1')) if lr else '–'} | {cell(lr.get('P2')) if lr else '–'} | "
              f"{lr['P1/P2'] if lr else '–'} | {where('v9', rid)} |")




def change():
    """Per re-tested rule, both wordings pooled: disagreement rate (flips / union) in v9 and in each later test, and
    Phase 1 / Phase 2 stable disagreements. Class (cut chosen here): better = pooled rate falls by 0.05 or more and
    P1/P2 does not rise; worse = pooled rate rises by 0.05 or more; else mixed."""
    sys.stdout.reconfigure(encoding="utf-8")
    d = json.loads((HERE / "ambiguity_by_rule.json").read_text(encoding="utf-8"))["A per wording and test"]
    cls = Counter()
    print("| Rule | " + " | ".join(VARIANTS) + " | P1/P2 v9 -> latest | class |")
    print("|---|" + "---|" * len(VARIANTS) + "---|---|")
    for rid, row in sorted(d.items()):
        tests = [v for v in VARIANTS if v in row]
        if len(tests) < 2:
            continue

        def pooled(v):
            f = sum(row[v][p]["flips"] for p in ("P1", "P2") if p in row[v])
            u = sum(row[v][p]["decided (union)"] for p in ("P1", "P2") if p in row[v])
            return f / u if u else None
        rates = {v: pooled(v) for v in tests}
        last = tests[-1]
        dr = rates[last] - rates["v9"]
        c = ("better" if dr <= -0.05 and row[last]["P1/P2"] <= row["v9"]["P1/P2"] else "worse" if dr >= 0.05 else "mixed")
        cls[c] += 1
        print(f"| {rid} {row['title']} | " + " | ".join(f"{rates[v]:.2f}" if v in rates else "" for v in VARIANTS)
              + f" | {row['v9']['P1/P2']} -> {row[last]['P1/P2']} | {c} |")
    print(dict(cls))


if __name__ == "__main__":
    {"--table": table, "--change": change}.get((sys.argv[1:] or [""])[0], main)()
