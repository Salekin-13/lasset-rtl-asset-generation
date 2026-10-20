"""Did the Walk-found internals rule fire in two_phase_v9k? (after run_v9k.py measure: the gate failed, precision unchanged.)
  F1 rule words in the Phase 2 replies per run (rows of any label, Not Reported rows, No Primary Reason text) that contain
     "walk-found", "path to the primary", "does not locate" or "located": v9k against v9j (v9j has no such rule).
  F2 v9k's walk-found false internals (strict anchoring, as run_v9k K2), per run: how many a keep list spares, how many the
     model's justification claims as stored / held / computed here, the rest; with examples (module:element, the concept's
     held lines, the element's assignment lines, the justification).
  F3 per-module listed and correct, v9k minus v9j, pooled over three runs (where the extra listings sit).
  python -B read_v9k_fire.py
"""
import json
import re
import sys
from collections import Counter, defaultdict

import run_v9k as K
import fp_v9j_detail as FD

V, CH, TR = K.V, K.CH, FD.TR
WORDS = ("walk-found", "path to the primary", "does not locate", "phase 1 entry", "located")
CLAIM = re.compile(r"\b(stor|held|hold|comput|register|clocked)", re.I)


def texts(v, m, r):
    d = K.load(v, m, r, "phase2")
    if d is None:
        return []
    rep = d["reply"]
    out = []
    for x in rep.get("structural assets") or []:
        if isinstance(x, dict):
            out.append(("row " + str(x.get("label")), x.get("element"), " ".join(str(x.get(k) or "") for k in ("justification", "reason", "functionality"))))
    for x in rep.get("not reported") or []:
        if isinstance(x, dict):
            out.append(("not reported", x.get("element"), str(x.get("reason") or "")))
    npr = rep.get("no primary reason") or {}
    for cid, s in (npr.items() if isinstance(npr, dict) else []):
        out.append(("no primary reason", cid, str(s)))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = V.R10.CV.groups_and_ref()
    mods = list(g["tuning"]) + list(g["held-out"])
    spared = __import__("sim_walk_rule").spared_set()
    out = {}
    # F1
    f1 = {}
    for v in (K.V9K, K.V9J):
        per = []
        for r in K.REPS:
            c = Counter()
            for m in mods:
                for kind, el, t in texts(v, m, r):
                    tl = t.lower()
                    if any(w in tl for w in WORDS):
                        c[kind] += 1
            per.append(dict(c))
        f1[v] = per
    out["F1 rule words per run (rows by label, Not Reported, No Primary Reason)"] = f1
    # F2
    f2, examples = [], []
    for r in K.REPS:
        cls = Counter()
        for m in mods:
            a, p1 = K.load(K.V9K, m, r, "assets"), K.load(K.V9K, m, r, "phase1")
            if a is None:
                continue
            al = FD.assign_lines(m)
            kd, _ = TR.kinds(m)
            concepts = {x["id"]: x for x in (p1["reply"].get("conceptual assets") or []) if isinstance(x, dict) and x.get("id")}
            left = Counter(x["Asset RTL"] for x in a["Assets"])
            ok = Counter()
            for n in ref[m]:
                if left[n] > 0:
                    left[n] -= 1
                    ok[n] += 1
            just = {(x.get("element")): str(x.get("justification") or x.get("reason") or "") for x in (K.load(K.V9K, m, r, "phase2")["reply"].get("structural assets") or []) if isinstance(x, dict) and x.get("label") == "primary"}
            seen = Counter()
            for row in a["Assets"]:
                e = row["Asset RTL"]
                seen[e] += 1
                if kd.get(e, "?") not in K.INTERNAL or seen[e] <= ok[e]:
                    continue
                cids = row.get("Concepts") or []
                strict = any(e in set(concepts.get(c, {}).get("enters through") or []) | set(concepts.get(c, {}).get("leaves through") or []) or (al.get(e, set()) & set(concepts.get(c, {}).get("held lines") or [])) for c in cids)
                if strict:
                    continue
                j = just.get(e, "")
                if f"{m}:{e}" in spared:
                    k = "spared by a keep list"
                elif CLAIM.search(j):
                    k = "justification claims stored / held / computed here"
                else:
                    k = "other"
                cls[k] += 1
                if len(examples) < 24 and k != "spared by a keep list":
                    hl = sorted(set().union(*[set(concepts.get(c, {}).get("held lines") or []) for c in cids])) if cids else []
                    examples.append(f"r{r} {m[8:]}:{e} | held lines {hl[:12]} | assigned at {sorted(al.get(e, set()))[:8]} | {j[:170]}")
        f2.append(dict(cls))
    out["F2 v9k walk-found false internals per run, by class"] = f2
    out["F2 examples"] = examples
    # F3
    delta = {}
    for m in mods:
        d = {"listed": 0, "correct": 0}
        for v, sign in ((K.V9K, 1), (K.V9J, -1)):
            for r in K.REPS:
                sc = V.R10.CV.C8.score(v, r, m, ref)
                if sc:
                    d["listed"] += sign * sc[0]
                    d["correct"] += sign * sc[1]
        delta[m[8:]] = d
    out["F3 per-module v9k minus v9j (3 runs): listed, correct; largest moves"] = sorted(delta.items(), key=lambda t: -abs(t[1]["listed"]))[:12]
    (K.HERE / "read_v9k_fire.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, v in out.items():
        if k == "F2 examples":
            print(k)
            for e in v:
                print("  " + e)
        else:
            print(k, json.dumps(v, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
