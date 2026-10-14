"""Effects of the user-decision restriction rules (workflow v4a-restrict-extra-concepts) alone and together with the A
and B rules of RULES_PROPOSAL.md, on the stored v4a concepts. Same conservative counting as rule_effects.py (benefit:
both judges agree; loss: either judge). Each restriction rule is scored on the judgments of its latest round.

  python u_effects.py <restriction workflow result or journal>     (writes u_effects.json)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rule_effects as RE  # noqa: E402

RUNS = ("r0", "r1", "r2")
RANK = {"removed": 3, "narrowed": 2, "merged": 1}


def load_u(path):
    if path.endswith("journal.jsonl"):
        raise SystemExit("use the result file; the round structure is assembled by the workflow")
    R = json.loads(Path(path).read_text(encoding="utf-8"))
    return R.get("result", R)


def combine(pairs, mode):
    eff = {}
    for judged, rid in pairs:
        for c, v in RE.effects_of(judged, rid, mode).items():
            if c not in eff:
                eff[c] = v
            else:
                w = v if RANK[v[0]] > RANK[eff[c][0]] else eff[c]
                eff[c] = (w[0], eff[c][1] | v[1], w[2])
    return eff


def measure(key, P, pairs):
    good, bad = combine(pairs, "both"), combine(pairs, "either")
    g, b = RE.tally(key, good, P), RE.tally(key, bad, P)
    out = {}
    for k in RUNS:
        emptied = 0
        for c, v in key.items():
            if c.split(":")[1] != k or not v["extra"]:
                continue
            e = good.get(c)
            if e and (e[0] in ("removed", "merged") or (e[0] == "narrowed" and set(v["prim"]) and set(v["prim"]) <= set(e[1]))):
                emptied += 1
        out[k] = {"extras": emptied, "fp": g[k]["fp_removed"], "lost": b[k]["tp_lost"], "P": g[k]["P"], "R": b[k]["R"],
                  "mrem": sorted(c for c, v in bad.items() if c.split(":")[1] == k and c in key and not key[c]["extra"] and v[0] in ("removed", "merged"))}
    return out


def main(path):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    key = json.loads((HERE / "boundary_key.json").read_text(encoding="utf-8"))
    P = json.loads((HERE / "pack3.json").read_text(encoding="utf-8"))
    U = load_u(path)
    W = json.loads((HERE / "rules_workflow_result.json").read_text(encoding="utf-8"))
    W = W.get("result", W)
    rounds = {h["round"]: h for h in U["history"]}
    upairs = {}
    for f in U["final"]:
        if f["status"] == "dropped":
            continue
        upairs[f["id"]] = (rounds[f["round"]]["judged"], f["id"])
    res = {"per_rule": {}, "sets": {}}
    print("rule    extras removed  FPs removed   lost      matched removed  precision after")
    for rid, pr in upairs.items():
        m = measure(key, P, [pr])
        res["per_rule"][rid] = m
        print(f"{rid:7s} {'/'.join(str(m[k]['extras']) for k in RUNS):14s}  {'/'.join(str(m[k]['fp']) for k in RUNS):12s}  "
              f"{'/'.join(str(len(m[k]['lost'])) for k in RUNS):8s}  {'/'.join(str(len(m[k]['mrem'])) for k in RUNS):15s}  "
              f"{'/'.join(format(m[k]['P'], '.3f') for k in RUNS)}  {[m[k]['lost'] for k in RUNS if m[k]['lost']]}")
    A = [(W["judged"], r) for r in ("R1", "R3", "R4", "R5", "K1", "K2")]
    B = [(W["judged"], r) for r in ("R2b", "R7b")]
    Upass = [pr for rid, pr in upairs.items() if not any(res["per_rule"][rid][k]["lost"] for k in RUNS)]
    for name, pairs in (("A", A), ("A+B", A + B), ("U (passing)", Upass), ("A+B+U", A + B + Upass)):
        m = measure(key, P, pairs)
        res["sets"][name] = m
        print(f"{name:12s} extras {'/'.join(str(m[k]['extras']) for k in RUNS):10s} FPs {'/'.join(str(m[k]['fp']) for k in RUNS):12s} "
              f"lost {'/'.join(str(len(m[k]['lost'])) for k in RUNS):7s} matched removed {'/'.join(str(len(m[k]['mrem'])) for k in RUNS):7s} "
              f"P {'/'.join(format(m[k]['P'], '.3f') for k in RUNS)}  R {'/'.join(format(m[k]['R'], '.3f') for k in RUNS)}")
    res["passing_u"] = [rid for rid, pr in upairs.items() if pr in Upass]
    res["dropped_u"] = [f["id"] for f in U["final"] if f["status"] == "dropped"]
    (HERE / "u_effects.json").write_text(json.dumps(res, indent=1, default=list), encoding="utf-8")
    print("passing U rules:", res["passing_u"], "| dropped in the loop:", res["dropped_u"])


if __name__ == "__main__":
    main(sys.argv[1])
