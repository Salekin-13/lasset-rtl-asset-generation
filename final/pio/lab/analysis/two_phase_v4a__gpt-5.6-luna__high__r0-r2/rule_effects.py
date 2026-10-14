"""Effects of the candidate rules (workflow v4a-extra-concept-rules) on the stored v4a concepts, computed from the blind
judges' decisions and the hidden key (boundary_key.json; exact scorer facts).

Conservative on both sides:
  benefit (extras removed, false positives removed) counts a concept effect only when BOTH judges give it (for 'narrowed',
  only primaries both judges drop);
  harm (correct finds lost, matched concepts hit) counts an effect when EITHER judge gives it.
An element is gone from a run when no concept of that run still lists it as primary after the effects ('merged' moves a
concept's primaries into its merged_into concept). A false positive is removed when it is gone; a correct find is lost when
it is gone. Recovery rules: new pieces classified as the target reference concept count as target hits; pieces with no
reference counterpart count as added extra concepts (per judge; the larger count is reported).
Precision after a rule = (correct - lost) / (listed - FP removed - correct lost), recall = (correct - lost) / 109; both are
arithmetic on stored replies, not predictions of a new run.
Self-test: an empty rule changes nothing; a rule that removes one concept loses exactly that concept's sole correct finds.
Writes rule_effects.json.

  python rule_effects.py <workflow result file or journal.jsonl>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ("r0", "r1", "r2")
TARGET = {"cpu": "RC8", "trng": "RC5"}


def load(path):
    if path.endswith("journal.jsonl"):
        label, res = {}, {}
        for line in open(path, encoding="utf-8"):
            d = json.loads(line)
            if d["type"] == "started":
                label[d["agentId"]] = d["label"]
            elif d["type"] == "result" and d.get("agentId") in label:
                r = d["result"]
                res[label[d["agentId"]]] = json.loads(r) if isinstance(r, str) and r[:1] in "{[" else r
        mods = sorted({k.split(":")[1] for k in res if k.startswith("rb-j1:")})
        final = (res.get("rules-skeptic") or {}).get("rules") or res["rules-merge"]["rules"]
        judged = [{"module": m, "judges": [res.get(f"rb-j1:{m}"), res.get(f"rb-j2:{m}")], "classified": res.get(f"rb-cls:{m}")} for m in mods]
        return {"final": final, "judged": judged}
    R = json.loads(Path(path).read_text(encoding="utf-8"))
    return R.get("result", R)


def apply(key, effects_by_concept):
    """effects_by_concept: {'mod:run:Cn': ('removed'|'narrowed'|'merged', dropped set, merged_into)} -> per run gone elements"""
    holders = defaultdict(set)                    # (mod, run, element) -> concepts listing it as primary
    for c, v in key.items():
        m, k, _ = c.split(":")
        for e in v["prim"]:
            holders[(m, k, e)].add(c)
    new_holders = {x: set(cs) for x, cs in holders.items()}
    for c, (eff, dropped, into) in effects_by_concept.items():
        m, k, _ = c.split(":")
        prims = set(key[c]["prim"]) if c in key else set()
        drop = prims if eff in ("removed", "merged") else (set(dropped) & prims)
        for e in drop:
            new_holders[(m, k, e)].discard(c)
            if eff == "merged" and into:
                tgt = f"{m}:{k}:{into.split(':')[-1]}"
                if tgt in key and effects_by_concept.get(tgt, ("",))[0] != "removed":
                    new_holders[(m, k, e)].add(tgt)
    gone = {x for x, cs in new_holders.items() if holders[x] and not cs}
    status = {}
    for c, v in key.items():
        m, k, _ = c.split(":")
        for e, s in v["prim"].items():
            status[(m, k, e)] = "tp" if s.startswith("tp") else "fp"
    return gone, status


def tally(key, eff, P):
    gone, status = apply(key, eff)
    out = {}
    for k in RUNS:
        fp_rm = sum(1 for x in gone if x[1] == k and status[x] == "fp")
        tp_lost = sorted(f"{x[0]}:{x[2]}" for x in gone if x[1] == k and status[x] == "tp")
        ex_rm = sum(1 for c, (e, _, _) in eff.items() if c.split(":")[1] == k and e in ("removed", "merged") and key.get(c, {}).get("extra"))
        hit = sorted(c for c, (e, _, _) in eff.items() if c.split(":")[1] == k and c in key and not key[c]["extra"])
        t = P["totals"][k]
        tp, listed = t["tp"] - len(tp_lost), t["listed"] - fp_rm - len(tp_lost)
        out[k] = {"extras_removed": ex_rm, "fp_removed": fp_rm, "tp_lost": tp_lost, "matched_hit": hit,
                  "P": tp / listed if listed else 0, "R": tp / 109}
    return out


def effects_of(judged, rid, mode):
    """mode 'both' = agreed by both judges (benefit); 'either' = union (harm)"""
    eff = {}
    for jm in judged:
        js = [j for j in jm["judges"] if j]
        per = []
        for j in js:
            d = {}
            for r in j["rules"]:
                if r["rule_id"] != rid:
                    continue
                for e in r["effects"]:
                    c = f"{jm['module']}:{e['concept'].strip()}"
                    d[c] = (e["effect"], set(e["dropped_primaries"]), e.get("merged_into", ""))
            per.append(d)
        if not per:
            continue
        if mode == "either":
            # harm: the worse effect wins (removed > narrowed > merged); dropped sets are joined
            rank = {"removed": 3, "narrowed": 2, "merged": 1}
            for d in per:
                for c, v in d.items():
                    if c not in eff:
                        eff[c] = v
                    else:
                        w = v if rank[v[0]] > rank[eff[c][0]] else eff[c]
                        eff[c] = (w[0], eff[c][1] | v[1], w[2])
        else:
            if len(per) < 2:
                continue
            for c in set(per[0]) & set(per[1]):
                a, b = per[0][c], per[1][c]
                kinds = {a[0], b[0]}
                if a[0] == b[0]:
                    eff[c] = (a[0], a[1] & b[1], a[2] if a[2] == b[2] else "")
                elif kinds == {"removed", "merged"}:
                    eff[c] = ("merged", set(), a[2] or b[2])          # both take the concept away; merged keeps its primaries
                elif kinds == {"removed", "narrowed"}:
                    n = a if a[0] == "narrowed" else b
                    eff[c] = ("narrowed", set(n[1]), "")             # both drop the narrowed judge's primaries
                # merged vs narrowed: no agreed effect
    return eff


def main(path):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    key = json.loads((HERE / "boundary_key.json").read_text(encoding="utf-8"))
    P = json.loads((HERE / "pack3.json").read_text(encoding="utf-8"))
    # self-test
    base = tally(key, {}, P)
    assert all(base[k]["fp_removed"] == 0 and not base[k]["tp_lost"] for k in RUNS)
    c0 = next(c for c, v in key.items() if any(s == "tp_sole" for s in v["prim"].values()))
    t0 = tally(key, {c0: ("removed", set(), "")}, P)
    sole = sorted(f"{c0.split(':')[0]}:{e}" for e, s in key[c0]["prim"].items() if s == "tp_sole")
    assert t0[c0.split(":")[1]]["tp_lost"] == sole, (t0, sole)
    m0, k0, _ = c0.split(":")
    other = next(c for c in key if c != c0 and c.startswith(f"{m0}:{k0}:"))
    t1 = tally(key, {c0: ("merged", set(), other.split(":")[-1])}, P)
    assert t1[k0]["tp_lost"] == [] and t1[k0]["extras_removed"] == (1 if key[c0]["extra"] else 0), t1[k0]
    W = load(path)
    rules = {r["id"]: r for r in W["final"]}
    out = {}
    print("rule  cat  kind       extras removed  FPs removed   correct lost  matched hit  P after (r0/r1/r2)   targets")
    for rid, r in rules.items():
        good = tally(key, effects_of(W["judged"], rid, "both"), P)
        bad = tally(key, effects_of(W["judged"], rid, "either"), P)
        rec = {"r0": 0, "r1": 0, "r2": 0}
        hits, new_extra = defaultdict(set), defaultdict(int)
        for jm in W["judged"]:
            cl = (jm.get("classified") or {}).get("pieces", [])
            per_j = defaultdict(lambda: defaultdict(int))
            for p in cl:
                if p["rule_id"] != rid:
                    continue
                if p["rc"] in ("none", "", "-"):
                    per_j[p["judge"]][p["run"]] += 1
                elif TARGET.get(jm["module"]) == p["rc"]:
                    hits[p["run"]].add(p["judge"])
            for k in RUNS:
                new_extra[k] += max((per_j[j][k] for j in per_j), default=0)
        out[rid] = {"rule": r, "benefit": good, "harm": bad, "target_hits": {k: sorted(hits[k]) for k in RUNS}, "new_extras": dict(new_extra)}
        ex = "/".join(str(good[k]["extras_removed"]) for k in RUNS)
        fp = "/".join(str(good[k]["fp_removed"]) for k in RUNS)
        lost = "/".join(str(len(bad[k]["tp_lost"])) for k in RUNS)
        mh = "/".join(str(len(bad[k]["matched_hit"])) for k in RUNS)
        pa = "/".join(f"{good[k]['P']:.3f}" for k in RUNS)
        extra = ""
        if r["kind"] == "recovery":
            extra = f" target hit in runs {[k for k in RUNS if hits[k]]}; new extras {'/'.join(str(new_extra[k]) for k in RUNS)}"
        print(f"{rid:5s} {r['category'][0]}    {r['kind']:10s} {ex:14s}  {fp:12s}  {lost:12s}  {mh:11s}  {pa:20s} {', '.join(r['targets'])[:40]}{extra}")
    (HERE / "rule_effects.json").write_text(json.dumps(out, indent=1, default=list), encoding="utf-8")
    print("\nwrote rule_effects.json")


if __name__ == "__main__":
    main(sys.argv[1])
