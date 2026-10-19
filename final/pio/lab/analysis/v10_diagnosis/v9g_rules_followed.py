"""Per rule: were its targets followed in the full two_phase_v9g prompt? (user 2026-10-18: "see the 3 run results on v9g
and use the finding to modify the cluster ordering plan ... increase the chance of the rules being followed"). Read-only;
writes v9g_rules_followed.json. Sends nothing.

Per rule of v9g_targets.json (N21-N25, P1-04, P1-14, P1-15; the last two were not adopted but their targets are read):
  found per run      targets found (exact scorer: the reference entry once per run) in v9g, v9f and v9 (r0-r2);
  stage of each miss transitions.where_lost's first-that-applies stage (secondary, not reported, Not Kept, parent or
                     field listed, anchor only, lines only, never named), so a rule whose targets are "secondary" lost
                     them in Phase 2's labelling, one whose targets are "never named" or "Not Kept" lost them in Phase 1;
  per module         correct finds per module and run, v9g against v9f, pooled over the three runs (gains and losses).
Self-test: the per-run correct totals equal run_v9g.recall_rows' for v9g, v9f and v9 (same scorer), and the per-rule
found counts summed over distinct targets equal run_v9g's R3 counts.

  python -B v9g_rules_followed.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE  # noqa: E402

import run_v9g as RG  # noqa: E402

V, HR, TR = RG.V, RG.HR, RG.TR
VERS = {"v9g": RG.V9G, "v9f": RG.V9F, "v9": RG.V9}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = RG.groups()
    ho = list(g["held-out"])
    tg = json.loads((HERE / "v9g_targets.json").read_text(encoding="utf-8"))
    by_rule = defaultdict(list)
    for rid, c in tg:
        if c not in by_rule[rid]:
            by_rule[rid].append(c)
    out = {"per rule": {}, "per module": {}}
    for rid, cases in by_rule.items():
        row = {"targets": len(cases), "found per run": {}, "misses": {}}
        for tag, v in VERS.items():
            found, stages = [], []
            for r in (0, 1, 2):
                n = 0
                for c in cases:
                    m, e = "neorv32_" + c.split(":")[0], c.split(":", 1)[1]
                    ls = HR.names(v, r, m)
                    if ls is None:
                        continue
                    hit = HR.found_occ(ref[m], ls).get((e, 1))
                    n += bool(hit)
                    if not hit and tag == "v9g":
                        stages.append((c, r, TR.where_lost(v, r, m, e, ls)[0]))
                found.append(n)
            row["found per run"][tag] = found
            if tag == "v9g":
                st = defaultdict(list)
                for c, r, s in stages:
                    st[c].append(f"r{r}: {s}")
                row["misses"] = dict(st)
                row["miss stages (entry-runs)"] = dict(Counter(s for _, _, s in stages))
        out["per rule"][rid] = row
    # per module, v9g vs v9f
    tot = {tag: [0, 0, 0] for tag in VERS}
    for m in ho:
        per = {}
        for tag, v in VERS.items():
            cs = []
            for r in (0, 1, 2):
                ls = HR.names(v, r, m)
                c = sum(HR.found_occ(ref[m], ls).values()) if ls is not None else None
                cs.append(c)
                if c is not None:
                    tot[tag][r] += c
            per[tag] = cs
        out["per module"][m[8:]] = {"reference": len(ref[m]), **per,
                                    "v9g - v9f pooled": sum(x for x in per["v9g"] if x is not None) - sum(x for x in per["v9f"] if x is not None)}
    # self-tests
    want = {tag: [x["correct"] for x in RG.recall_rows(v, (0, 1, 2), ho)] for tag, v in VERS.items()}
    ok = all(tot[tag] == want[tag] for tag in VERS)
    r3 = RG.readers(RG.V9G, (0, 1, 2))["R3 targets found per run (of %d)" % len(RG.targets())]
    mine = [sum(bool(RG.found(RG.V9G, r, c)) for c in RG.targets()) for r in (0, 1, 2)]
    ok &= mine == r3["candidate"]
    print(f"self-test (per-run totals {tot} = run_v9g {want}; R3 {mine} = {r3['candidate']}): {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)
    out["self-test"] = "PASS"
    (HERE / "v9g_rules_followed.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for rid, row in out["per rule"].items():
        print(f"{rid:6} targets {row['targets']:2} | found per run v9g {row['found per run']['v9g']} v9f {row['found per run']['v9f']} v9 {row['found per run']['v9']} | miss stages {row.get('miss stages (entry-runs)')}")
    gains = sorted(out["per module"].items(), key=lambda t: -t[1]["v9g - v9f pooled"])
    print("per module v9g - v9f pooled:", [(m, x["v9g - v9f pooled"]) for m, x in gains if x["v9g - v9f pooled"]])


if __name__ == "__main__":
    main()
