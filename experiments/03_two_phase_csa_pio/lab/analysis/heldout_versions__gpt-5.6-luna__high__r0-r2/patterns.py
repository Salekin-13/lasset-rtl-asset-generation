"""Patterns behind the held-out change, per prompt rule, read from attribute.json and transitions.json (both made from
the stored replies by code). Read-only; writes patterns.json.

1. Lost finds by rule: for every Phase 1 rule that a reply names for a held-out reference element it misses, in a
   version step where that element is found in fewer runs than before (attribute.py, "lost find-runs"), the element's
   runs found in each version v1 ... v8, and the rule's first version. An element counts under a rule when the rule
   is named for it in at least 2 missing runs (one run may be noise). Summed per rule: runs found per version.
2. Ports that turn secondary with no rule named: held-out reference ports lost in a step (2+ of 3 runs -> at most 1,
   transitions.py) whose missing runs are mostly "secondary" rows and whose replies name no rule there.
3. False positives by element kind and module (held-out, v4a, v5, v7, v8): which kinds the rules removed and which stay.
Self-test: the per-version sums of runs found equal the counts recomputed from the assets files.

  python patterns.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import transitions as T  # noqa: E402

CV, CH = T.CV, T.CH
VERS = CV.VERS


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    groups, ref = CV.groups_and_ref()
    at = json.loads((HERE / "attribute.json").read_text(encoding="utf-8"))
    tr = json.loads((HERE / "transitions.json").read_text(encoding="utf-8"))
    listed = {(v, r, m): [x["Asset RTL"] for x in json.loads((CH.run_dir(v, T.MODEL, r, T.EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]]
              for v in VERS for r in T.REPS for m in groups["held-out"]}

    def runs_found(el):          # el = "module:name" -> runs found per version (first reference occurrence)
        mod, n = el.split(":", 1)
        m = "neorv32_" + mod
        return {v[10:]: sum(1 for r in T.REPS if n in listed[(v, r, m)]) for v in VERS}

    # 1. rules named for lost finds (held-out), elements with the rule named in 2+ missing runs
    named = defaultdict(Counter)
    for p, res in at["pairs"].items():
        b = p.split(" -> ")[1]
        for el_rule, _ in []:
            pass
    # recount per element and rule from the examples is lossy; re-tag the missing runs of each step's losing elements
    for p, res in at["pairs"].items():
        for rule, els in res["held-out"]["lost find-runs"]["elements by rule"].items():
            if rule == "(no rule named)":
                continue
            for el in els:
                named[rule][el] += 1          # steps in which the rule is named for the element
    by_rule = {}
    for rule, els in named.items():
        rows = {}
        for el in sorted(els):
            mod, n = el.split(":", 1)
            m = "neorv32_" + mod
            # missing runs naming the rule, over all versions that have it
            k = 0
            for v in VERS:
                if T_rule_in(v, rule):
                    for r in T.REPS:
                        if n in listed[(v, r, m)]:
                            continue
                        st, why = T.where_lost(v, r, m, n, listed[(v, r, m)])
                        if rule in A.tag(v, r, m, n, why):
                            k += 1
            if k >= 2:
                rows[el] = {"runs found per version": runs_found(el), "missing runs naming the rule": k}
        if rows:
            tot = Counter()
            for x in rows.values():
                tot.update(x["runs found per version"])
            by_rule[rule] = {"first in": at["rule first in"].get(rule), "elements": rows,
                             "runs found, summed": {v[10:]: tot[v[10:]] for v in VERS}}
    # 2. ports turning secondary with no rule named
    ports = {}
    for p, pr in tr["pairs"].items():
        for o, x in pr["held-out"]["lost"].items():
            key = [k for k in x if k.startswith("where lost")][0]
            st = Counter(s for _, s, _ in x[key])
            el = o.split("#")[0]
            if x["kind"][0] != "port" or st["secondary"] < max(1, sum(st.values()) / 2):
                continue
            if any(el in els for rule, els in at["pairs"][p]["held-out"]["lost find-runs"]["elements by rule"].items() if rule != "(no rule named)"):
                continue
            ports.setdefault(el, {"step": p, "runs found per version": runs_found(el),
                                  "a justification": x[key][0][2][0][:220] if x[key][0][2] else ""})
    # self-test: runs_found equals the per-occurrence counts transitions.py used (first occurrence)
    ok = True
    for p, pr in tr["pairs"].items():
        a, b = p.split(" -> ")
        for o, x in pr["held-out"]["lost"].items():
            if not o.endswith("#1"):
                continue
            f = runs_found(o.split("#")[0])
            want = [int(y) for y in x["runs found"].split(" -> ")]
            ok &= [f[a], f[b]] == want
    print("self-test (runs found = transitions.json for every lost first occurrence):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    print("\n1. held-out finds lost under a rule the replies name (runs found of 3, per version)")
    print(f"   {'':40s}" + "".join(f"{v[10:]:>5s}" for v in VERS))
    for rule, z in sorted(by_rule.items(), key=lambda kv: -sum(kv[1]["runs found, summed"].values())):
        print(f"   {rule + ' (first in ' + str(z['first in']) + ')':40s}" + "".join(f"{z['runs found, summed'][v[10:]]:5d}" for v in VERS) + "   <- summed")
        for el, x in z["elements"].items():
            print(f"     {el:38s}" + "".join(f"{x['runs found per version'][v[10:]]:5d}" for v in VERS) + f"   (rule named in {x['missing runs naming the rule']} missing runs)")
    print("\n2. held-out ports lost as 'secondary' with no rule named")
    for el, x in ports.items():
        print(f"   {el:38s}" + "".join(f"{x['runs found per version'][v[10:]]:5d}" for v in VERS) + f"   step {x['step']}: {x['a justification'][:150]}")
    # 3. FP kinds by module (held-out)
    fpk = defaultdict(Counter)
    for m in groups["held-out"]:
        kd, par = T.kinds(m)
        for v in VERS:
            for r in T.REPS:
                left = Counter(ref[m])
                for x in listed[(v, r, m)]:
                    if left[x] > 0:
                        left[x] -= 1
                        continue
                    k = kd.get(x, "not in closed set")
                    if k == "port field":
                        k = "bus record port field" if (par.get(x, (None, None))[1] or "").startswith(("bus_req", "bus_rsp")) else "other record port field"
                    fpk[(v, k)][m[8:]] += 1
    print("\n3. held-out FPs of v7 by kind: modules holding most (v4a / v5 / v7 / v8)")
    fp_out = {}
    for k in ("other record port field", "signal field", "signal", "port"):
        top = fpk[("two_phase_v7", k)].most_common(6)
        fp_out[k] = {m: {v[10:]: fpk[(v, k)][m] for v in VERS} for m, _ in top}
        print(f"   {k}: " + "; ".join(f"{m} {fpk[('two_phase_v4a', k)][m]}/{fpk[('two_phase_v5', k)][m]}/{c}/{fpk[('two_phase_v8', k)][m]}" for m, c in top))
    (HERE / "patterns.json").write_text(json.dumps({"lost finds by rule": by_rule, "ports turned secondary, no rule named": ports,
                                                    "v7 held-out FPs by kind, top modules": fp_out}, indent=1), encoding="utf-8")
    print("\nwritten patterns.json")


def T_rule_in(v, rule):
    return rule.split(" (")[0] in A.titles(v)


import attribute as A  # noqa: E402

if __name__ == "__main__":
    main()
