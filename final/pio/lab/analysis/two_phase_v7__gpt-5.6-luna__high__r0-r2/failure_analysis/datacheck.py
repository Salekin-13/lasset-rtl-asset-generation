"""Steps 1a and 1b: is every v7 run complete, and are there format failures?

1a (compare_condensed.complete): per run, an assets file for each of the 15 modules, no pending request, no failed
   call, no re-ask (a first reply moved to _schema_failed/). Also both phase files exist for every module.
1b, on the replies as written (raw):
   - rows without their name key: a concept without "Concept ID", a Not Kept row without "Candidate Name", a walk
     without "Concept ID", a point without "Point", an asset row without "Asset RTL", a Not Reported row without
     "Element RTL";
   - rows nested in the wrong place: "Assets" or "Not Reported" written inside a point (the v5g r0 bus slip);
   - walks missing for kept concepts, and walks for concept ids Phase 1 did not keep;
   - every "format:" and "consistency:" note chain.from_format_phase1/2 gives (reported apart: they are notes, not
     failures that lose rows).
   Repaired score (adapted from the v5g folder's repair_and_targets.py): the nested rows are read as walk-level rows
   and the reply is converted again with chain.to_assets. Nothing else can be repaired (a missing walk has no rows).
Self-test: the strict per-run totals recomputed here from the assets files equal compare_v7.runs(); the nesting
detector finds the known slip in v5g r0 bus (10 walks with empty walk-level Assets, hand-read in format_v5g.py) and
none in v6 r0 wdt.

Writes datacheck.json.   python datacheck.py
"""
import json
import sys
from collections import Counter

import common_fa as F

CH, K = F.CH, F.K


def nested_walks(p2):
    out = []
    for w in p2.get("Concept Walks", []) or []:
        if not isinstance(w, dict):
            continue
        for p in w.get("Points") or []:
            if isinstance(p, dict) and (isinstance(p.get("Assets"), list) or isinstance(p.get("Not Reported"), list)):
                out.append(w.get("Concept ID"))
                break
    return out


def scan(version, r, m):
    run = CH.run_dir(version, F.MODEL, r, F.EFF)
    rec1 = json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8"))
    rec2 = json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))
    p1, p2 = K.parse_json(rec1["raw"]), K.parse_json(rec2["raw"])
    fails = []
    cons = p1.get("Conceptual Assets", []) or []
    for i, c in enumerate(cons):
        if not isinstance(c, dict) or not c.get("Concept ID"):
            fails.append(f"phase 1 concept #{i + 1} without 'Concept ID'")
    for i, x in enumerate(p1.get("Not Kept", []) or []):
        if not isinstance(x, dict) or not x.get("Candidate Name"):
            fails.append(f"phase 1 Not Kept row #{i + 1} without 'Candidate Name'")
    ids = [c.get("Concept ID") for c in cons if isinstance(c, dict)]
    walks = [w for w in (p2.get("Concept Walks", []) or [])]
    have = []
    for i, w in enumerate(walks):
        if not isinstance(w, dict) or not w.get("Concept ID"):
            fails.append(f"phase 2 walk #{i + 1} without 'Concept ID'")
            continue
        have.append(w["Concept ID"])
        for j, p in enumerate(w.get("Points") or []):
            if not isinstance(p, dict) or not p.get("Point"):
                fails.append(f"phase 2 walk {w['Concept ID']} point #{j + 1} without 'Point'")
        for j, a in enumerate(w.get("Assets") or []):
            if not isinstance(a, dict) or not a.get("Asset RTL"):
                fails.append(f"phase 2 walk {w['Concept ID']} asset row #{j + 1} without 'Asset RTL'")
        for j, x in enumerate(w.get("Not Reported") or []):
            if not isinstance(x, dict) or not x.get("Element RTL"):
                fails.append(f"phase 2 walk {w['Concept ID']} Not Reported row #{j + 1} without 'Element RTL'")
    for cid in nested_walks(p2):
        fails.append(f"phase 2 walk {cid}: rows written inside a point")
    for cid in ids:
        if cid not in have:
            fails.append(f"phase 2: no walk for kept concept {cid}")
    for cid in have:
        if cid not in ids:
            fails.append(f"phase 2: walk for {cid}, which Phase 1 did not keep")
    _, a = CH.from_format_phase1(p1, rec1["raw"])
    _, b = CH.from_format_phase2(p2, rec2["raw"], ids)
    notes = [f"p1 {x}" for x in a] + [f"p2 {x}" for x in b]
    return fails, notes, (p1, p2, rec1, rec2)


def repaired_assets(m, p1, p2, rec1):
    fixed = json.loads(json.dumps(p2))
    for w in fixed.get("Concept Walks", []):
        inner = []
        for p in w.get("Points", []):
            for key in ("Assets", "Not Reported"):
                if isinstance(p.get(key), list):
                    (inner if key == "Assets" else w.setdefault("Not Reported", [])).extend(p.pop(key))
        seen, rows = set(), []
        for x in (w.get("Assets") or []) + inner:
            k = json.dumps(x, sort_keys=True)
            if k not in seen:
                seen.add(k)
                rows.append(x)
        w["Assets"] = rows
    v1, _ = CH.from_format_phase1(p1, rec1["raw"])
    concepts = CH.phase1_concepts(v1)
    v2, _ = CH.from_format_phase2(fixed, "", [c.get("id") for c in concepts])
    return CH.to_assets(m, v2, concepts)["Assets"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # self-tests
    _, _, (p1, p2, _, _) = scan("two_phase_v5g", 0, "neorv32_bus")
    t1 = sum(1 for w in p2["Concept Walks"] if not w.get("Assets")) == 10 and len(nested_walks(p2)) >= 1
    _, _, (p1, p2, _, _) = scan("two_phase_v6", 0, "neorv32_wdt")
    t2 = not nested_walks(p2)
    runs = F.C7.runs(F.VERSION, F.REPS)
    strict = {}
    for r in F.REPS:
        T = L = 0
        for m in F.MODS:
            l, t, _, _ = F.CC.score(F.VERSION, r, m)
            T, L = T + t, L + l
        strict[r] = (T, L)
    t3 = all(strict[r] == (runs[r]["correct"], runs[r]["listed"]) for r in F.REPS)
    print(f"self-test: nesting detector finds v5g r0 bus ({t1}) and not v6 r0 wdt ({t2}); strict totals = compare_v7.runs ({t3})")
    if not (t1 and t2 and t3):
        sys.exit("self-test failed: nothing written")
    comp = F.CC.complete(F.VERSION)
    both = {f"r{r}": [F.short(m) for m in F.MODS if not ((F.run_dir(r) / "phase1" / f"{m}.json").exists() and (F.run_dir(r) / "phase2" / f"{m}.json").exists())] for r in F.REPS}
    out = {"1a completeness": {f"r{r}": comp[r] for r in F.REPS}, "1a modules missing a phase file": both}
    fails, notes, rep = {}, {}, {}
    for r in F.REPS:
        T = L = 0
        for m in F.MODS:
            f, n, (p1, p2, rec1, rec2) = scan(F.VERSION, r, m)
            if f:
                fails[f"r{r} {F.short(m)}"] = f
            if n:
                notes[f"r{r} {F.short(m)}"] = n
            if any("inside a point" in x for x in f):
                a = repaired_assets(m, p1, p2, rec1)
                listed = Counter(x["Asset RTL"] for x in a)
                t = 0
                for (_k, nm, _kk, _h) in F.ref_entries(m):
                    if listed[nm] > 0:
                        listed[nm] -= 1
                        t += 1
                T, L = T + t, L + len(a)
            else:
                l, t, _, _ = F.CC.score(F.VERSION, r, m)
                T, L = T + t, L + l
        rep[f"r{r}"] = {"correct": T, "listed": L, "precision": round(T / L, 3), "recall": round(T / 109, 3),
                        "strict correct": strict[r][0], "strict listed": strict[r][1]}
    kinds = Counter()
    for k, xs in notes.items():
        for x in xs:
            kinds[x.split(":")[0] + ": " + x.split(":", 2)[-1].split("'")[0].strip()[:60]] += 1
    out["1b format failures (lose or misplace rows)"] = fails or "none"
    out["1b format failures count"] = sum(len(v) for v in fails.values())
    out["1b repaired score (nested rows read as walk rows)"] = rep
    out["1b notes from chain's format check (not failures), count by kind"] = dict(kinds.most_common())
    # other slips: a required non-name field missing. Checked: does the walk of each such concept still name a primary?
    other = {}
    for k, xs in notes.items():
        r, sm = int(k.split()[0][1:]), "neorv32_" + k.split()[1]
        p2 = F.parsed(r, sm, 2)
        prim = {w.get("Concept ID"): any(isinstance(a, dict) and a.get("Label") == "primary" for a in (w.get("Assets") or []))
                for w in p2.get("Concept Walks", []) if isinstance(w, dict)}
        for x in xs:
            if " lacks " in x:
                cid = x.split("conceptual asset ")[1].split()[0] if "conceptual asset " in x else x.split("walk ")[1].split()[0]
                other.setdefault(k, []).append(x[3:] + f" | walk {cid} names a primary: {prim.get(cid)}")
    out["1b other slips: a required non-name field missing (rows kept)"] = other
    out["1b other slips count"] = sum(len(v) for v in other.values())
    out["1b notes per reply"] = notes
    (F.HERE / "datacheck.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "1b notes per reply"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
