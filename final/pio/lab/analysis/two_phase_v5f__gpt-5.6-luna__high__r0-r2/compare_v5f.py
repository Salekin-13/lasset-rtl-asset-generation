"""two_phase_v5f (v5 rules, new reply formats) vs two_phase_v5, gpt-5.6-luna, high, r0-r2, inputs v1. No model call.

Reads every reply as the model wrote it ("raw"), so the format is judged on the model's own text, not on chain.py's
mapping. Writes compare_v5f.json next to this file.

A. Format slip, measured the same way in both versions:
   rows: a Phase 2 asset row whose name key ("element" / "Asset RTL") is missing or empty; whose name is not a
         closed-set element of its entity; or that cannot be tied to a Phase 1 concept (v5: its "concept id"; v5f: its
         walk's "Concept ID"); "misplaced": the name key fails and another key of the row holds a closed-set name.
   points: the same for points ("point" / "Point" must be a block or output of the concept's unit).
   Phase 1: conceptual assets lacking a template key, or with an id that is not C<n>.
   v5f only: every format and consistency problem chain.from_format_phase1/2 report on the raw reply, by kind.
B. Accuracy, exact scorer (names equal, each listed element used once; 109 findable): per run, found-in-all-3,
   element-level changes, and the README's pre-set rules.
C. The new fields (v5f): walks with no primary, Not Reported, Merged Into.
D. Misses by the furthest place their name appears (v5: notes; v5f: Not Reported, No Primary Reason, Notes).
E. Size and cost per run.
Self-tests: v5 r1 bus has 67 asset rows, 57 without "element" (hand count, V5_RESULTS.md); a planted v5f reply with one
row lacking "Asset RTL", one invalid name and one point in an unknown walk is counted 1/1/1.

  python compare_v5f.py
"""
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402
import cost_estimate as CE  # noqa: E402

MODEL, EFF, RUNS = "gpt-5.6-luna", "high", (0, 1, 2)
V = {"v5": "two_phase_v5", "v5f": "two_phase_v5f"}
MODS = CH.tuning_modules()
P1_OLD = ("id", "unit", "concept", "information", "rubric", "rubric reason", "objectives", "attack", "enters through",
          "leaves through", "entry lines", "held lines", "exit lines")


def raw(v, r, ph, m):
    rec = json.loads((CH.run_dir(V[v], MODEL, r, EFF) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))
    return rec, K.parse_json(rec["raw"])


def p1_concepts(v, obj):
    """[(id, unit, concept dict)] from a raw Phase 1 reply."""
    if v == "v5":
        return [(c.get("id"), c.get("unit"), c) for c in obj.get("conceptual assets", []) if isinstance(c, dict)]
    return [(c.get("Concept ID"), c.get("Unit"), c) for c in obj.get("Conceptual Assets", []) if isinstance(c, dict)]


def p2_rows(v, obj):
    """(points, assets) from a raw Phase 2 reply, each item as (concept id, name or None, row dict)."""
    if v == "v5":
        return ([(p.get("concept id"), p.get("point"), p) for p in obj.get("points", []) if isinstance(p, dict)],
                [(a.get("concept id"), a.get("element"), a) for a in obj.get("structural assets", []) if isinstance(a, dict)])
    pts, ass = [], []
    for w in obj.get("Concept Walks", []):
        if not isinstance(w, dict):
            continue
        cid = w.get("Concept ID")
        pts += [(cid, p.get("Point"), p) for p in (w.get("Points") or []) if isinstance(p, dict)]
        ass += [(cid, a.get("Asset RTL"), a) for a in (w.get("Assets") or []) if isinstance(a, dict)]
    return pts, ass


def entity_of(v, a):
    return a.get("entity") if v == "v5" else a.get("Entity")


def slip_counts(v, m, p1, p2, names, units):
    ids = {cid: unit for cid, unit, _ in p1_concepts(v, p1)}
    pts, ass = p2_rows(v, p2)
    c = Counter()
    all_names = {n for (_, n) in names}
    for cid, name, a in ass:
        c["rows"] += 1
        no_name = not (isinstance(name, str) and name)
        invalid = not no_name and (entity_of(v, a), name) not in names
        untied = cid not in ids
        c["rows: no name"] += no_name
        c["rows: name not in closed set"] += invalid
        c["rows: not tied to a concept"] += untied
        c["rows: any of these"] += no_name or invalid or untied
        others = [x for k, x in a.items() if k not in ("element", "Asset RTL") and isinstance(x, str)]
        c["rows: misplaced name"] += (no_name or invalid) and any(x in all_names for x in others)
    blocks = {u: d["blocks"] | d["outputs"] for u, d in units.items()}
    for cid, name, p in pts:
        c["points"] += 1
        no_name = not (isinstance(name, str) and name)
        unit = ids.get(cid)
        invalid = not no_name and name not in blocks.get(unit, set().union(*blocks.values()) if blocks else set())
        untied = cid not in ids
        c["points: no name"] += no_name
        c["points: not a block or output of the unit"] += invalid
        c["points: not tied to a concept"] += untied
        c["points: any of these"] += no_name or invalid or untied
        others = [x for k, x in p.items() if k not in ("point", "Point") and isinstance(x, str)]
        c["points: misplaced name"] += (no_name or invalid) and any(x in set().union(*blocks.values()) for x in others)
    keys = P1_OLD if v == "v5" else CH.F1_CONCEPT
    for cid, _, cc in p1_concepts(v, p1):
        c["concepts"] += 1
        c["concepts: lacking a key"] += any(k not in cc for k in keys)
        c["concepts: bad id"] += not re.fullmatch(r"C\d+", str(cid))
    return c


def selftest():
    m = "neorv32_bus"
    _, p2 = raw("v5", 1, 2, m)
    _, p1 = raw("v5", 1, 1, m)
    rows = p2_rows("v5", p2)[1]
    ok1 = len(rows) == 67 and sum(1 for _, n, _ in rows if not n) == 57
    w = "neorv32_wdt"
    names, units = CH.closed_names(w), CH.diagram_names(w)
    p1f = {"Conceptual Assets": [{**{k: [] for k in CH.F1_CONCEPT}, "Concept ID": "C1", "Unit": w}]}
    p2f = {"Concept Walks": [
        {"Concept ID": "C1", "Points": [{"Point": "bus_access"}], "Assets": [{"Entity": w}, {"Asset RTL": "no_such", "Entity": w},
                                                                            {"Asset RTL": "ctrl.enable", "Entity": w}]},
        {"Concept ID": "C7", "Points": [{"Point": "bus_access"}], "Assets": []}]}
    c = slip_counts("v5f", w, p1f, p2f, names, units)
    ok2 = (c["rows: no name"], c["rows: name not in closed set"], c["points: not tied to a concept"], c["rows: any of these"]) == (1, 1, 1, 2)
    print(f"self-test: v5 r1 bus 57 of 67 rows without 'element': {ok1}; planted v5f counts 1/1/1: {ok2}")
    return ok1 and ok2


def sign_test(a, b):
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if not selftest():
        sys.exit("self-test failed: nothing reported")
    import eval_assets as ea
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    res = {}

    # ---------------- run integrity (v5f)
    integ = Counter()
    for r in RUNS:
        for m in MODS:
            for ph in (1, 2):
                rec = json.loads((CH.run_dir(V["v5f"], MODEL, r, EFF) / f"phase{ph}" / f"{m}.json").read_text(encoding="utf-8"))
                integ["records"] += 1
                integ["mapped by the new-format reader"] += "reply keys" in rec
                integ[f"phase {ph} system sha = v5f build"] += rec["system sha"] == CH.sha12(CH.C.system(V["v5f"], ph))
    print("\nrun integrity (v5f):", dict(integ))
    res["integrity"] = dict(integ)

    # ---------------- A. format slip
    print("\nA. FORMAT SLIP (replies with at least one / items), per run r0 / r1 / r2")
    A = {}
    for v in V:
        per = []
        for r in RUNS:
            tot, reps = Counter(), Counter()
            for m in MODS:
                _, p1 = raw(v, r, 1, m)
                _, p2 = raw(v, r, 2, m)
                c = slip_counts(v, m, p1, p2, CH.closed_names(m), CH.diagram_names(m))
                tot += c
                for k, n in c.items():
                    reps[k] += n > 0
            per.append({"items": dict(tot), "replies with any": dict(reps)})
        A[v] = per
    keys = ["rows: no name", "rows: name not in closed set", "rows: not tied to a concept", "rows: misplaced name",
            "rows: any of these", "points: no name", "points: not a block or output of the unit",
            "points: not tied to a concept", "points: misplaced name", "points: any of these",
            "concepts: lacking a key", "concepts: bad id"]
    for k in keys:
        cells = []
        for v in V:
            cells.append(f"{v}: " + " / ".join(f"{A[v][i]['replies with any'].get(k, 0)}r {A[v][i]['items'].get(k, 0)}" for i in range(3)))
        print(f"  {k:42s} " + "   |   ".join(cells))
    for v in V:
        print(f"  denominators {v}: rows " + " / ".join(str(A[v][i]["items"]["rows"]) for i in range(3))
              + ", points " + " / ".join(str(A[v][i]["items"]["points"]) for i in range(3))
              + ", concepts " + " / ".join(str(A[v][i]["items"]["concepts"]) for i in range(3)) + "; replies 15 per run and phase")
    res["A"] = A
    # v5f: every format / consistency problem chain reports on the raw replies
    kinds = [Counter(), Counter(), Counter()]
    kind_reps = [Counter(), Counter(), Counter()]
    examples = defaultdict(list)
    for i, r in enumerate(RUNS):
        for m in MODS:
            rec1, p1 = raw("v5f", r, 1, m)
            rec2, p2 = raw("v5f", r, 2, m)
            _, pr1 = CH.from_format_phase1(p1, rec1["raw"])
            ids = [c[0] for c in p1_concepts("v5f", p1)]
            _, pr2 = CH.from_format_phase2(p2, rec2["raw"], ids)
            seen = set()
            for ph, pr in ((1, pr1), (2, pr2)):
                for x in pr:
                    k = f"phase {ph} " + re.sub(r"(walk|conceptual asset|not-kept entry) \S+( (point|asset|not-reported entry) .+?)? ",
                                                lambda mm: f"{mm.group(1)}{' ' + mm.group(3) if mm.group(3) else ''} ", x)
                    k = re.sub(r"\[.*?\]|'.*?'|\(.*?\)", "…", k)
                    kinds[i][k] += 1
                    if k not in seen:
                        kind_reps[i][k] += 1
                        seen.add(k)
                    if len(examples[k]) < 2:
                        examples[k].append(f"r{r} {m.replace('neorv32_', '')}: {x[:160]}")
    allk = sorted(set().union(*kinds), key=lambda k: -sum(kc[k] for kc in kinds))
    print("\n  v5f format and consistency problems reported on the raw replies (replies with it / count), r0 / r1 / r2:")
    for k in allk:
        print(f"    {k[:110]:110s} " + " / ".join(f"{kind_reps[i][k]}r {kinds[i][k]}" for i in range(3)))
        for e in examples[k][:1]:
            print(f"        e.g. {e}")
    if not allk:
        print("    none")
    res["A v5f problems"] = {k: [kinds[i][k] for i in range(3)] for k in allk}
    res["A v5f problem replies"] = {k: [kind_reps[i][k] for i in range(3)] for k in allk}

    # ---------------- B. accuracy
    print("\nB. ACCURACY (exact; recall of 109)")
    found = {v: defaultdict(int) for v in V}
    B = {}
    for v in V:
        B[v] = []
        for r in RUNS:
            L = T = 0
            for m in MODS:
                a = json.loads((CH.run_dir(V[v], MODEL, r, EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))
                listed = Counter(x["Asset RTL"] for x in a["Assets"])
                L += sum(listed.values())
                names = {n for (_, n) in CH.closed_names(m)}
                kth = Counter()
                for name, _ in refs[m]:
                    if name not in names:
                        continue
                    kth[name] += 1
                    if listed[name] > 0:
                        listed[name] -= 1
                        T += 1
                        found[v][f"{m.replace('neorv32_', '')}:{name}#{kth[name]}"] += 1
            p, rc = T / L, T / 109
            B[v].append({"listed": L, "correct": T, "fp": L - T, "precision": round(p, 3), "recall": round(rc, 3),
                         "f1": round(2 * p * rc / (p + rc), 3)})
            print(f"  {v:4s} r{r}: listed {L} correct {T} FP {L - T}  precision {p:.3f}  recall {rc:.3f}  F1 {2 * p * rc / (p + rc):.3f}")
    allel = set(found["v5"]) | set(found["v5f"])
    all3 = {v: sum(found[v][e] == 3 for e in allel) for v in V}
    more = sorted(e for e in allel if found["v5f"][e] > found["v5"][e])
    fewer = sorted(e for e in allel if found["v5f"][e] < found["v5"][e])
    lost = sorted(e for e in allel if found["v5"][e] == 3 and found["v5f"][e] <= 1)
    print(f"  found in all 3 runs: v5 {all3['v5']}, v5f {all3['v5f']} (of 109)")
    print(f"  elements found in more v5f runs: {len(more)}; in fewer: {len(fewer)}; sign test p = {sign_test(len(more), len(fewer)):.2f}")
    print("    more :", ", ".join(f"{e.split('#')[0]} {found['v5'][e]}->{found['v5f'][e]}" for e in more))
    print("    fewer:", ", ".join(f"{e.split('#')[0]} {found['v5'][e]}->{found['v5f'][e]}" for e in fewer))
    lowp, lowr = min(x["precision"] for x in B["v5"]), min(x["recall"] for x in B["v5"])
    below = sum(x["precision"] < lowp or x["recall"] < lowr for x in B["v5f"])
    print(f"  pre-set rule 1: runs with precision below v5's lowest ({lowp}) or recall below v5's lowest ({lowr}): {below} of 3"
          f" -> {'FALSIFIED' if below >= 2 else 'not falsified'}")
    print(f"  pre-set rule 2: elements in all 3 v5 runs found in at most 1 v5f run: {len(lost)} {[e.split('#')[0] for e in lost]}"
          f" -> {'FALSIFIED' if len(lost) >= 3 else 'not falsified'}")
    res["B"] = {"runs": B, "all3": all3, "more": more, "fewer": fewer, "lost": lost, "rule1 runs below": below,
                "found": {v: dict(found[v]) for v in V}}

    # ---------------- C. new fields (v5f)
    print("\nC. NEW FIELDS (v5f), r0 / r1 / r2")
    C = []
    for r in RUNS:
        c = Counter()
        for m in MODS:
            _, p1 = raw("v5f", r, 1, m)
            _, p2 = raw("v5f", r, 2, m)
            kept = {x[0] for x in p1_concepts("v5f", p1)}
            for x in p1.get("Not Kept", []) or []:
                if isinstance(x, dict):
                    c["not kept"] += 1
                    c["not kept: merged"] += bool(x.get("Merged Into"))
                    c["not kept: merged into an unknown id"] += bool(x.get("Merged Into")) and x.get("Merged Into") not in kept
            for w in p2.get("Concept Walks", []) or []:
                if not isinstance(w, dict):
                    continue
                c["walks"] += 1
                ass = [a for a in (w.get("Assets") or []) if isinstance(a, dict)]
                prim = any(a.get("Label") == "primary" for a in ass)
                npr = w.get("No Primary Reason")
                c["walks with no primary"] += not prim
                c["  of them with a No Primary Reason"] += (not prim) and isinstance(npr, str) and bool(npr.strip())
                c["walks with a primary and a No Primary Reason"] += prim and isinstance(npr, str) and bool(npr.strip())
                nr = [x for x in (w.get("Not Reported") or []) if isinstance(x, dict)]
                c["Not Reported entries"] += len(nr)
                here = {(a.get("Entity"), a.get("Asset RTL")) for a in ass}
                c["Not Reported entries also under Assets"] += sum((x.get("Element Entity"), x.get("Element RTL")) in here for x in nr)
                for a in ass:
                    c["asset rows"] += 1
                    c["asset rows with an empty Functionality"] += not (isinstance(a.get("Functionality"), str) and a["Functionality"].strip())
                    c["asset rows with an empty Justification"] += not (isinstance(a.get("Justification"), str) and a["Justification"].strip())
        C.append(c)
    for k in sorted(set().union(*C), key=lambda k: list(C[0]).index(k) if k in C[0] else 99):
        print(f"  {k:48s} " + " / ".join(str(C[i][k]) for i in range(3)))
    res["C"] = [dict(c) for c in C]

    # ---------------- D. misses by the furthest place the name appears
    def has(name, text):
        return bool(re.search(r"(?<![\w.])" + re.escape(name) + r"(?!\w)(?!\.\w)", text or ""))
    print("\nD. MISSES by the furthest place the name appears (all 3 runs)")
    D = {}
    for v in V:
        st = Counter()
        for r in RUNS:
            for m in MODS:
                _, p1 = raw(v, r, 1, m)
                _, p2 = raw(v, r, 2, m)
                listed = Counter(x["Asset RTL"] for x in json.loads((CH.run_dir(V[v], MODEL, r, EFF) / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"])
                names = {n for (_, n) in CH.closed_names(m)}
                pts, ass = p2_rows(v, p2)
                lab = "label" if v == "v5" else "Label"
                sec = {n for _, n, a in ass if a.get(lab) == "secondary" and isinstance(n, str)}
                if v == "v5":
                    sec |= {x for _, _, a in ass if a.get("label") == "secondary" for x in (a.get("same role") or []) if isinstance(x, str)}
                    nrep, npr = "", ""
                    notes = " ".join(map(str, p2.get("notes", [])))
                else:
                    sec |= {x for _, _, a in ass if a.get("Label") == "secondary" for x in (a.get("Same Role") or []) if isinstance(x, str)}
                    ws = [w for w in p2.get("Concept Walks", []) if isinstance(w, dict)]
                    nrep = " ".join(f"{x.get('Element RTL')} {x.get('Why Not Reported')}" for w in ws for x in (w.get("Not Reported") or []) if isinstance(x, dict))
                    npr = " ".join(str(w.get("No Primary Reason", "")) for w in ws)
                    notes = " ".join(map(str, p2.get("Notes", [])))
                bad = {str(a.get("concept id")) for _, n, a in ass if not n} if v == "v5" else {
                    x for _, n, a in ass if not n for x in a.values() if isinstance(x, str)}
                rtext = " ".join(json.dumps(a, ensure_ascii=False) for _, _, a in ass)
                ptext = " ".join(json.dumps(p, ensure_ascii=False) for _, _, p in pts)
                p1t = json.dumps(p1, ensure_ascii=False)
                for name, _ in refs[m]:
                    if name not in names:
                        continue
                    if listed[name] > 0:
                        listed[name] -= 1
                        continue
                    s = ("1 labelled secondary" if name in sec else "2 in a row without its name key" if name in bad
                         else "3 Not Reported" if has(name, nrep) else "4 No Primary Reason" if has(name, npr)
                         else "5 Phase 2 notes" if has(name, notes) else "6 other text of an asset row" if has(name, rtext)
                         else "7 at a point" if has(name, ptext) else "8 Phase 1 only" if has(name, p1t) else "9 nowhere")
                    st[s] += 1
        D[v] = dict(st)
        print(f"  {v:4s} misses {sum(st.values())}: " + ", ".join(f"{k[2:]} {st[k]}" for k in sorted(st)))
    res["D"] = D

    # ---------------- E. size and cost
    print("\nE. SIZE AND COST per run r0 / r1 / r2")
    P = CE.PRICES[MODEL]
    E = {}
    for v in V:
        rows = []
        for r in RUNS:
            c = Counter()
            for m in MODS:
                rec1, p1 = raw(v, r, 1, m)
                rec2, p2 = raw(v, r, 2, m)
                c["concepts"] += len(p1_concepts(v, p1))
                pts, ass = p2_rows(v, p2)
                c["points"] += len(pts)
                c["asset rows"] += len(ass)
                for ph, rec in ((1, rec1), (2, rec2)):
                    u = rec["usage"]
                    c[f"out tokens phase {ph}"] += u["out"]
                    c["usd"] += ((u["in"] - (u.get("cached") or 0)) * P["in"] + (u.get("cached") or 0) * P["cached"] + u["out"] * P["out"]) / 1e6
            rows.append(c)
        E[v] = [dict(x) for x in rows]
        for k in ("concepts", "points", "asset rows", "out tokens phase 1", "out tokens phase 2", "usd"):
            print(f"  {v:4s} {k:20s} " + " / ".join(f"{x[k]:.2f}" if k == "usd" else f"{x[k]:,}" for x in rows))
    res["E"] = E
    (HERE / "compare_v5f.json").write_text(json.dumps(res, indent=1, default=list), encoding="utf-8")
    print("\nwritten:", HERE / "compare_v5f.json")


if __name__ == "__main__":
    main()
