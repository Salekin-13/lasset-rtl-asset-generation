"""Would the rule-isolation run on the worst modules only serve the same purpose as the run on all 41? Code only,
read-only on runs; nothing is sent. Writes subset_check.json.

Per module, from the v9 full-prompt runs r0-r2 (rule_consistency.py's extractor, reused unchanged):
  mixed       (element, rule) pairs where the rule was cited to exclude the element in some run and the element was
              primary in another run (the rule followed in one run, ignored in another)
  P1 vs P2    element-runs barred by a Phase 1 rule yet primary in Phase 2 of the same run
  cited       (element, rule) pairs where the rule was cited at all (followed, any class)
  breaks      mixed + P1 vs P2
Modules are ranked by breaks. For the worst-k set (k = smallest set holding 80% of all breaks):
  - each isolation rule: modules of the set where v9 cited it, and its share of its own mixed cases inside the set;
    rules with no citation in the set get no test there
  - the pilot (wdt, cpu_icc): were the rules the pilot flagged cited or mixed there in v9?
  - cost: input tokens per request by isolation.preview's method (calibrated pre-token floor), output at the pilot's
    measured mean per call (an estimate: output for the large modules is not measured yet)
Self-test: the recomputed mixed cases and P1-vs-P2 element-runs equal rule_consistency.json, rule by rule.

  python -B subset_check.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONS = HERE.parent / "two_phase_v9__gpt-5.6-luna__high__r0-r2" / "consistency"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CONS))
import isolation as ISO  # noqa: E402
import rule_consistency as RC  # noqa: E402

CH, K = ISO.CH, ISO.K
REPS = (0, 1, 2)
TITLE_OF = {"P1-22R": "Operation selectors", "P2X-bus-request-response-record-port": "2.6 bus record port bar"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, ref = RC.CV.groups_and_ref()
    split = {m: "tuning" for m in groups["tuning"]} | {m: "held-out" for m in groups["held-out"]}
    mods = groups["tuning"] + groups["held-out"]
    listed = {(r, m): [x["Asset RTL"] for x in json.loads((CH.run_dir(RC.V9, RC.T.MODEL, r, RC.T.EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]
              for r in REPS for m in mods}
    rules = RC.rules_for(RC.V9)
    cite = defaultdict(lambda: defaultdict(set))
    for m in mods:
        for r in REPS:
            for n, rr, kind in RC.citations(RC.V9, r, m, rules):
                cite[(m, n, rr)][kind.replace(" (line link)", "")].add(r)
    mixed = defaultdict(Counter)          # m -> rule -> mixed pairs
    p1p2 = defaultdict(Counter)           # m -> rule -> element-runs barred in P1, primary in P2
    cited = defaultdict(Counter)          # m -> rule -> cited pairs
    for (m, n, rr), kinds in cite.items():
        excl = set().union(*(kinds.get(k, set()) for k in ("P1 Not Kept", "P2 secondary", "P2 not reported")))
        pr = {r for r in REPS if n in listed[(r, m)]}
        cited[m][rr] += 1
        if excl and pr:
            mixed[m][rr] += 1
        p1p2[m][rr] += len(kinds.get("P1 Not Kept", set()) & pr)
    # self-test against rule_consistency.json
    rcj = json.loads((CONS / "rule_consistency.json").read_text(encoding="utf-8"))
    want_mixed = Counter(c["rule"] for c in rcj["B mixed cases"])
    got_mixed = Counter()
    got_c = Counter()
    for m in mods:
        got_mixed.update(mixed[m])
        got_c.update(p1p2[m])
    want_c = Counter({rr: sum(d.get(s, {}).get("element-runs barred in Phase 1 yet primary in Phase 2", 0) for s in ("tuning", "held-out"))
                      for rr, d in rcj["C cross-phase contradictions"].items()})
    ok = +got_mixed == +want_mixed and +got_c == +want_c
    print(f"self-test (mixed cases and P1-vs-P2 element-runs = rule_consistency.json, per rule): {'PASS' if ok else 'FAIL'}"
          f" | mixed {sum(got_mixed.values())} vs {sum(want_mixed.values())}, P1 vs P2 {sum(got_c.values())} vs {sum(want_c.values())}")
    if not ok:
        print("  diff mixed:", dict((got_mixed - want_mixed) + (want_mixed - got_mixed)), "diff C:", dict((got_c - want_c) + (want_c - got_c)))
        sys.exit(1)
    # per module
    rows = []
    for m in mods:
        tp = fp = 0
        fn = 0
        for r in REPS:
            left = Counter(ref[m])
            for x in listed[(r, m)]:
                if left[x] > 0:
                    left[x] -= 1
                    tp += 1
                else:
                    fp += 1
            fn += sum(left.values())
        b = sum(mixed[m].values()) + sum(p1p2[m].values())
        rows.append({"module": m, "split": split[m], "TP runs": tp, "FP runs": fp, "FN runs": fn,
                     "precision": round(tp / (tp + fp), 3) if tp + fp else None, "recall": round(tp / (tp + fn), 3) if tp + fn else None,
                     "mixed": sum(mixed[m].values()), "P1 vs P2": sum(p1p2[m].values()), "breaks": b,
                     "rules cited": len(cited[m]), "rules broken": len(set(mixed[m]) | {r for r, v in p1p2[m].items() if v})})
    rows.sort(key=lambda x: -x["breaks"])
    tot = sum(x["breaks"] for x in rows)
    cum, worst = 0, []
    for x in rows:
        worst.append(x["module"])
        cum += x["breaks"]
        if cum >= 0.8 * tot:
            break
    print(f"\nall breaks: {tot} (mixed {sum(x['mixed'] for x in rows)}, P1 vs P2 {sum(x['P1 vs P2'] for x in rows)}) over {len(mods)} modules; "
          f"80% sit in the worst {len(worst)}")
    print(f"{'module':28s} split     P      R     breaks mixed P1vsP2 rules-broken rules-cited")
    for x in rows:
        mark = "*" if x["module"] in worst else " "
        print(f"{mark}{x['module'][8:]:27s} {x['split']:8s} {x['precision']!s:6s} {x['recall']!s:6s} {x['breaks']:5d} {x['mixed']:5d} {x['P1 vs P2']:6d} "
              f"{x['rules broken']:6d} {x['rules cited']:6d}")
    # coverage per isolation rule
    texts = json.loads((HERE / "rule_texts.json").read_text(encoding="utf-8"))
    cov = {}
    W = set(worst)
    for rid, t in texts.items():
        title = TITLE_OF.get(rid, t["title"])
        keys = [k for k in rules if k == title or k.startswith(title + " (")]
        if not keys:
            cov[rid] = {"title": t["title"], "v9 citation data": False}
            continue
        allm = {m for m in mods if any(cited[m][k] for k in keys)}
        allmix = sum(mixed[m][k] + p1p2[m][k] for m in mods for k in keys)
        inmix = sum(mixed[m][k] + p1p2[m][k] for m in W for k in keys)
        cov[rid] = {"title": t["title"], "v9 citation data": True, "modules citing it (all)": len(allm),
                    "modules citing it (worst set)": len(allm & W), "breaks (all)": allmix, "breaks in the worst set": inmix,
                    "modules where it broke, outside the worst set": sorted(m[8:] for m in mods if m not in W and any(mixed[m][k] + p1p2[m][k] for k in keys))}
    print(f"\ncoverage of each isolation rule by the worst {len(worst)} modules")
    for rid, c in cov.items():
        if not c["v9 citation data"]:
            print(f"  {rid:44s} {c['title'][:34]:34s} no v9 citation data (the v9 keyword tagger has no key for it)")
        else:
            print(f"  {rid:44s} {c['title'][:34]:34s} cited in {c['modules citing it (worst set)']:2d}/{c['modules citing it (all)']:2d} modules; "
                  f"breaks inside {c['breaks in the worst set']:3d}/{c['breaks (all)']:3d}; broke outside: {c['modules where it broke, outside the worst set'][:6]}")
    # the pilot
    print("\npilot modules in v9 (rules the pilot flagged)")
    for m in ISO.PILOT:
        r = next(x for x in rows if x["module"] == m)
        print(f"  {m[8:]}: rank {rows.index(r) + 1} of {len(rows)} by breaks ({r['breaks']}); "
              + "; ".join(f"{k}: cited {cited[m][k]}, mixed {mixed[m][k]}, P1 vs P2 {p1p2[m][k]}"
                          for k in ("Working values", "Port buffers", "Buffer and engine status bits")))
    wdt = "neorv32_wdt"
    for n in ("cnt_started", "cnt_inc", "prsc_tick"):
        print(f"    wdt:{n}: in the reference {n in ref[wdt]}; primary in v9 runs {[r for r in REPS if n in listed[(r, wdt)]]}")
    # cost
    quiet = lambda *a, **k: None  # noqa: E731
    meas = ISO.measured(ISO.jobs(None, reps=(0, 1))[0], log=quiet)
    mo = meas["mean out"]
    import cost_estimate as CE
    P = CE.PRICES["gpt-5.6-luna"]

    def usd(modules):
        jl, tx = ISO.jobs(modules, reps=(0, 1))
        p = ISO.preview(jl, tx, log=quiet)
        if not p["to send"]:
            return 0.0, 0
        u2 = p["usd by output per call"][2000]
        base_in = u2 - p["to send"] * 2000 * P["out"] / 1e6
        return round(base_in + p["to send"] * mo * P["out"] / 1e6, 2), p["to send"]
    full = usd(None)
    sub = usd(worst)
    print(f"\ncost estimate (input from the calibrated pre-token count, output at the pilot mean {mo:,.0f} tokens per call):"
          f"\n  all 41 modules: {full[1]} requests, about USD {full[0]}\n  worst {len(worst)}: {sub[1]} requests, about USD {sub[0]}")
    (HERE / "subset_check.json").write_text(json.dumps({"modules": rows, "worst set (80% of breaks)": worst, "coverage": cov,
                                                        "cost": {"all": full, "worst": sub, "output per call used": mo}},
                                                       indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
