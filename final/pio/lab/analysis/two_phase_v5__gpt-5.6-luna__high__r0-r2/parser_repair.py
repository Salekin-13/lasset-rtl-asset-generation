"""Scores with the parser repair proposed by the v5 diagnosis (wf_1aa19284-7f0), next to the strict scores.

Some Phase 2 rows put the element name in 'concept id' and leave out 'element'; the converter drops them (strict scoring,
the rule used since v1). pack3.json lists them as 'malformed rows' when the name is a closed-set element of the row's
entity. Repaired scoring reads those rows: a primary malformed row adds its element to the run's list (once); it is
correct when its name matches a reference entry of that module not yet matched in the run (each entry once, as in the
strict scorer), else a false positive.
Both readings are reported; strict stays the main number. Writes parser_repair.json.

  python parser_repair.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
RUNS = ("r0", "r1", "r2")
V = {"v3": "two_phase_v3__gpt-5.6-luna__high__r0-r2", "v4": "two_phase_v4__gpt-5.6-luna__high__r0-r2",
     "v4a": "two_phase_v4a__gpt-5.6-luna__high__r0-r2", "v5": "two_phase_v5__gpt-5.6-luna__high__r0-r2"}


def repaired(P):
    out, added = {}, {}
    for k in RUNS:
        listed, tp = P["totals"][k]["listed"], P["totals"][k]["tp"]
        add = []
        for m, d in P["modules"].items():
            r = d["runs"][k]
            have = {(x["entity"], x["element"]) for x in r["listed"]}
            # reference entries not yet matched in this run, by name (a name can have several entries, e.g. two 'state');
            # like the strict scorer, each entry is matched once
            free = Counter(e["name"] for e in d["reference entries"] if not e["absent"] and e["entry"] not in r["tp"])
            for x in r["malformed rows"]:
                if x["label"] != "primary" or (x["entity"], x["element"]) in have:
                    continue
                have.add((x["entity"], x["element"]))
                listed += 1
                ok = free[x["element"]] > 0
                if ok:
                    tp += 1
                    free[x["element"]] -= 1
                add.append((m.replace("neorv32_", ""), x["element"], "TP" if ok else "FP"))
        out[k] = {"listed": listed, "tp": tp, "fp": listed - tp}
        added[k] = add
    return out, added


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = {}
    for v, d in V.items():
        P = json.loads((AN / d / "pack3.json").read_text(encoding="utf-8"))
        NF = P["entries"] - P["absent"]
        rep, added = repaired(P)
        res[v] = {"strict": {}, "repaired": {}, "added": added}
        for k in RUNS:
            s = P["totals"][k]
            r = rep[k]
            res[v]["strict"][k] = {"P": s["tp"] / s["listed"], "R": s["tp"] / NF, "tp": s["tp"], "listed": s["listed"]}
            res[v]["repaired"][k] = {"P": r["tp"] / r["listed"], "R": r["tp"] / NF, "tp": r["tp"], "listed": r["listed"]}
        print(f"{v:4s} strict   P " + " / ".join(f"{res[v]['strict'][k]['P']:.3f}" for k in RUNS) + "   R " + " / ".join(f"{res[v]['strict'][k]['R']:.3f}" for k in RUNS))
        print(f"{v:4s} repaired P " + " / ".join(f"{res[v]['repaired'][k]['P']:.3f}" for k in RUNS) + "   R " + " / ".join(f"{res[v]['repaired'][k]['R']:.3f}" for k in RUNS)
              + "   added: " + "; ".join(f"{k} {sum(1 for a in added[k] if a[2] == 'TP')} TP {sum(1 for a in added[k] if a[2] == 'FP')} FP" for k in RUNS))
    for k in RUNS:
        for a in res["v5"]["added"][k]:
            print(f"   v5 {k} added {a[0]}:{a[1]} ({a[2]})")
    # the README recall tests under the repair
    rr = [res["v4a"]["repaired"][k]["R"] for k in RUNS]
    below = [k for k in RUNS if res["v5"]["repaired"][k]["R"] < min(rr)]
    print(f"\nrepaired: v5 recall below v4a's repaired range ({min(rr):.3f}-{max(rr):.3f}) in runs {below or 'none'}")
    (HERE / "parser_repair.json").write_text(json.dumps(res, indent=1, default=list), encoding="utf-8")


if __name__ == "__main__":
    main()
