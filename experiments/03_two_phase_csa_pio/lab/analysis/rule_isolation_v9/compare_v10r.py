"""Rewritten critical rules ("v10r") against their v9 wordings, each rule applied alone (cell 12 vs cell 11 of
experiments/03_two_phase_csa_pio/two_phase_asset_identification.ipynb). Code only, read-only on the runs; writes compare_v10r.json.

Per rule wording, v9 -> v10r (same 41 modules, 2 repeats, same reply format; analyze_isolation.py and clause_check.py
measures, unchanged):
  two readings     contradictions whose two runs quote different clauses of the rule (clause_check.classify, run on
                   each variant's own rule text)
  format           contradictions quoting the same clause, filed on opposite lists
  one-sided        decided in one run, not mentioned in the other (other run listed others / listed nothing)
  applied once     modules where one run decided something and the other nothing
  unsure           modules with an "unsure" entry
  stable           decisions in both runs; of them, reference elements by exact name
  P1/P2            stable Phase 1 / Phase 2 disagreements and phase contradictions (analyze_isolation)
Per bar with a code-defined pattern (pattern_coverage.scan, v7 detectors over all 41 modules): signals barred in both
runs, v9 -> v10r. Per v8 design target the rule decides: kept / barred runs, v9 -> v10r.

Readings set before the run (2026-10-15; cuts chosen, stated as such):
  R1 reworded rules: two-reading contradictions fall by at least half per rule (both wordings summed), and no wording
     has two readings in 3 or more modules.
  R2 restructured-only rules (Sequencing state, Port options, Per-region checks, Second copies): one-sided differences
     and applied-once modules fall. (Whether what remains is over-application needs readers again; ask first.)
  R3 no bar loses more than one signal of its code-defined pattern (barred in both runs).
  R4 stable decisions on reference elements (exact name) do not rise for any rule.
  R5 decisions: D8 sys enable_i is barred by Pacing pulses (Phase 1) in neither run; D2 Forwarded transactions' Phase 2
     wording bars the merged bus responses (detector T5) in both runs; D3 Working values' phase contradictions fall.
  R6 Phase 1 / Phase 2 stable disagreements fall summed over the rules.
A rule failing R1, R3 or R4 goes back to the rewrite; R2 and R6 are read, not gated.
Self-test (nothing is reported if it fails): the v9 side reproduces isolation_report.json (flips, contradictions,
stable P1/P2 disagreements) and clause_contradictions.json (same / different clause counts) for every rewritten rule.

  python -B compare_v10r.py            (v9 side and self-test only, if no v10r replies are stored)
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "heldout_versions__gpt-5.6-luna__high__r0-r2"))
import isolation as ISO  # noqa: E402
import analyze_isolation as A  # noqa: E402
import clause_check as CC  # noqa: E402
import compare_versions as CV  # noqa: E402

CH, K = ISO.CH, ISO.K
REWORDED = ["P1-05", "P1-07", "P1-23", "P1-22", "P1-27", "P1-04", "P1-02", "P1-08", "P1-09", "P1-14", "P1-17", "P1-10", "P1-16"]
STRUCTURE_ONLY = ["P1-15", "P1-18", "P1-24", "P1-06"]


def load(variant, rules):
    ISO.use(variant)
    R = {k: v for k, v in A.load(lambda r: ISO.run_root(rep=r)).items() if k[0] in rules}
    tf = ISO.texts_file()
    texts = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else {}
    ISO.use("v9")
    return R, texts


def measures(R, texts, rules, ref, prim):
    rep = A.analyze(R, prim, ref)
    out = {}
    for rid in rules:
        if rid not in rep:
            continue
        row = {"P1/P2 stable disagreements": len(rep[rid]["Phase 1 / Phase 2 stable disagreements"]),
               "phase contradictions": len(rep[rid]["phase contradictions"])}
        for ph in ("P1", "P2"):
            if ph not in rep[rid]:
                continue
            x = rep[rid][ph]
            same = diff = 0
            mods_diff = set()
            for m, e in CC.contradictions(R, rid, ph):
                k = CC.classify(R, texts, rid, ph, m, e)[0]
                same += k == "same clause"
                diff += k == "different clauses"
                if k == "different clauses":
                    mods_diff.add(m)
            have = [{k[2] for k in R if k[0] == rid and k[1] == ph and k[3] == r} for r in (0, 1)]
            left = empty = once = 0
            stable_ref = 0
            for m in sorted(have[0] & have[1]):
                D = [A.names(R[(rid, ph, m, r)], "spared" if A.adds(rid) else "barred") for r in (0, 1)]
                once += bool(D[0]) != bool(D[1])
                for a, b in ((0, 1), (1, 0)):
                    for e in D[a]:
                        if not A.covered(e, D[b]):
                            if D[b]:
                                left += 1
                            else:
                                empty += 1
                stable_ref += sum(1 for e in D[0] if A.covered(e, D[1]) and e in ref.get(m, set()))
            row[ph] = {"modules": x["modules"], "flips": x["flips"], "contradictions": x["contradictions"],
                       "two readings": diff, "two-reading modules": len(mods_diff), "format": same,
                       "one-sided (left out / other run empty)": [left, empty], "applied once": once,
                       "unsure modules": x["modules with unsure"], "stable": x["stable decisions (both repeats)"],
                       "stable on reference (exact)": stable_ref}
        out[rid] = row
    return out, rep


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rules = REWORDED + STRUCTURE_ONLY
    _, refl = CV.groups_and_ref()
    ref = {m: set(v) for m, v in refl.items()}
    prim = Counter()
    for m in ref:
        for r in (0, 1, 2):
            f = CH.run_dir(ISO.V9, "gpt-5.6-luna", r, "high") / "assets" / f"{m}.json"
            for n in {x["Asset RTL"] for x in json.loads(f.read_text(encoding="utf-8"))["Assets"]}:
                prim[(m, n)] += 1
    R9, T9 = load("v9", rules)
    m9, rep9 = measures(R9, T9, rules, ref, prim)
    # self-test against the stored v9 reports
    iso = json.loads((HERE / "isolation_report.json").read_text(encoding="utf-8"))
    cc = json.loads((HERE / "clause_contradictions.json").read_text(encoding="utf-8"))
    bad = []
    for rid in rules:
        for ph in ("P1", "P2"):
            if ph in iso.get(rid, {}):
                a, b = m9[rid][ph], iso[rid][ph]
                if (a["flips"], a["contradictions"]) != (b["flips"], b["contradictions"]):
                    bad.append(f"{rid} {ph} flips/contradictions")
                c = cc.get(f"{rid} {ph}")
                if c and (a["two readings"], a["format"]) != (c["different clauses"], c["same clause"]):
                    bad.append(f"{rid} {ph} clause classes")
        if m9[rid]["P1/P2 stable disagreements"] != len(iso[rid]["Phase 1 / Phase 2 stable disagreements"]):
            bad.append(f"{rid} P1/P2")
    print(f"self-test (v9 side reproduces isolation_report.json and clause_contradictions.json for {len(rules)} rules):",
          "PASS" if not bad else f"FAIL {bad}")
    if bad:
        sys.exit(1)
    R10, T10 = load("v10r", rules)
    n10 = len(R10)
    print(f"v10r replies stored: {n10}")
    if not n10:
        return
    m10, rep10 = measures(R10, T10, rules, ref, prim)
    print(f"\n{'rule':6s} {'title':30s} ph | two readings (modules) | format | one-sided left/empty | applied once | unsure | stable (ref) | v9 -> v10r")
    for rid in rules:
        for ph in ("P1", "P2"):
            if ph not in m9.get(rid, {}) or ph not in m10.get(rid, {}):
                continue
            a, b = m9[rid][ph], m10[rid][ph]
            print(f"{rid:6s} {T9[rid]['title'][:30]:30s} {ph} | {a['two readings']}({a['two-reading modules']}) -> {b['two readings']}({b['two-reading modules']}) | "
                  f"{a['format']} -> {b['format']} | {a['one-sided (left out / other run empty)']} -> {b['one-sided (left out / other run empty)']} | "
                  f"{a['applied once']} -> {b['applied once']} | {a['unsure modules']} -> {b['unsure modules']} | "
                  f"{a['stable']}({a['stable on reference (exact)']}) -> {b['stable']}({b['stable on reference (exact)']})")
    out = {"v9": m9, "v10r": m10}
    # readings
    rd = {}
    for rid in REWORDED:
        t9 = sum(m9[rid][ph]["two readings"] for ph in ("P1", "P2") if ph in m9[rid])
        t10 = sum(m10[rid][ph]["two readings"] for ph in ("P1", "P2") if ph in m10.get(rid, {}))
        mx = max([m10[rid][ph]["two-reading modules"] for ph in ("P1", "P2") if ph in m10.get(rid, {})] or [0])
        rd[rid] = {"R1 two readings v9 -> v10r": f"{t9} -> {t10}", "R1 pass": t10 <= t9 / 2 and mx < 3}
    for rid in STRUCTURE_ONLY:
        o9 = sum(sum(m9[rid][ph]["one-sided (left out / other run empty)"]) for ph in ("P1", "P2") if ph in m9[rid])
        o10 = sum(sum(m10[rid][ph]["one-sided (left out / other run empty)"]) for ph in ("P1", "P2") if ph in m10.get(rid, {}))
        a9 = sum(m9[rid][ph]["applied once"] for ph in ("P1", "P2") if ph in m9[rid])
        a10 = sum(m10[rid][ph]["applied once"] for ph in ("P1", "P2") if ph in m10.get(rid, {}))
        rd[rid] = {"R2 one-sided v9 -> v10r": f"{o9} -> {o10}", "R2 applied once": f"{a9} -> {a10}", "R2 fell": o10 < o9 and a10 <= a9}
    for rid in rules:
        r9 = sum(m9[rid][ph]["stable on reference (exact)"] for ph in ("P1", "P2") if ph in m9[rid])
        r10 = sum(m10[rid][ph]["stable on reference (exact)"] for ph in ("P1", "P2") if ph in m10.get(rid, {}))
        rd.setdefault(rid, {})["R4 stable on reference (exact) v9 -> v10r"] = f"{r9} -> {r10}"
        rd[rid]["R4 pass"] = r10 <= r9
    s9 = sum(m9[r]["P1/P2 stable disagreements"] for r in rules)
    s10 = sum(m10[r]["P1/P2 stable disagreements"] for r in rules if r in m10)
    out["readings"] = rd
    out["R6 P1/P2 stable disagreements v9 -> v10r"] = f"{s9} -> {s10}"
    # R3 patterns and R5 decisions
    import pattern_coverage as PC
    hits, ok, _ = PC.scan()
    pats = {}
    for fx, t, m, en, n in hits:
        key = (fx, t[0] if fx == "P3" else t)
        if key in PC.MAP and any(r in rules for r in PC.MAP[key]):
            pats.setdefault(key, set()).add((m, n))

    def both(R, rid, ph, m, n, key="barred"):
        if (rid, ph, m, 0) not in R or (rid, ph, m, 1) not in R:
            return None
        return all(A.covered(n, A.names(R[(rid, ph, m, r)], key)) for r in (0, 1))
    r3 = {}
    for key, inst in pats.items():
        rids = [r for r in PC.MAP[key] if r in rules]
        for ph in ("P1", "P2"):
            # only modules where both tests stored both runs of the rule (a missing reply is no loss)
            ok = [(m, n) for m, n in inst if all(both(RR, r, ph, m, n) is not None for RR in (R9, R10) for r in rids)]
            c9 = sum(1 for m, n in ok if any(both(R9, r, ph, m, n) for r in rids))
            c10 = sum(1 for m, n in ok if any(both(R10, r, ph, m, n) for r in rids))
            if c9 or c10:
                r3[f"{PC.LABEL[key]} ({ph})"] = {"v9": c9, "v10r": c10, "of": len(ok), "skipped (a reply missing)": len(inst) - len(ok),
                                                 "R3 pass": c10 >= c9 - 1}
    out["R3 patterns barred in both runs"] = r3
    r5 = {"D8 sys enable_i barred by Pacing pulses P1 (runs v9, v10r)": [
        sum(A.covered("enable_i", A.names(R.get(("P1-04", "P1", "neorv32_sys", r), {}), "barred")) for r in (0, 1)) for R in (R9, R10)],
          "D2 merged bus responses barred in both runs by Forwarded transactions P1 (v9, v10r; None = a reply missing)": [
        [both(R, "P1-05", "P1", m, n) for m, n in sorted(pats.get(("P2", "T5"), set()))].count(True) if all(both(R, "P1-05", "P1", m, n) is not None for m, n in pats.get(("P2", "T5"), set())) else None for R in (R9, R10)],
          "D2 merged bus responses barred in both runs by Forwarded transactions P2 (v9, v10r)": [
        sum(1 for m, n in pats.get(("P2", "T5"), set()) if both(R, "P1-05", "P2", m, n)) for R in (R9, R10)],
          "D3 Working values phase contradictions (v9, v10r)": [m9["P1-08"]["phase contradictions"], m10.get("P1-08", {}).get("phase contradictions")]}
    out["R5 decisions"] = r5
    (HERE / "compare_v10r.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("\nreadings:", json.dumps(rd, indent=1))
    print("R3:", json.dumps(r3, indent=1))
    print("R5:", json.dumps(r5, indent=1))
    print("R6 P1/P2 stable disagreements:", out["R6 P1/P2 stable disagreements v9 -> v10r"])


if __name__ == "__main__":
    main()
