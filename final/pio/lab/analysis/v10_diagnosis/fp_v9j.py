"""Where two_phase_v9j's false positives come from (user 2026-10-18: "analyze the failure patterns and find out why precision
is still low. is there any more ways that phase 1 can be modified to improve precision? or should we now move to phase 2?
in phase 2 modification, analyze if diagram analysis can be improved to reduce false positives?"). Read-only; sends nothing.

Data: two_phase_v9j r0-r2 on the 41 modules (assets files = the scored primaries; Phase 1 and Phase 2 replies; the closed
set; the diagram). An FP is a listed name left after the reference rows consume their copies (the exact scorer's
complement, fp_v9h.fps). Readings, fixed before the run:
  R1 totals and stability: FPs per group and run; FP elements listed in 3, 2 or 1 of the 3 runs; the share of FP
     occurrences that belong to 3-of-3 elements; FPs per module (concentration).
  R2 which phase owns each FP occurrence, from the concept(s) it is primary for:
     L1 "right concept, extra element": one of the concept's primaries is a reference entry  -> a Phase 2 choice;
     L2 "right concept, wrong element or label": no correct primary, but a reference entry is among the concept's
        secondaries, its Not Reported rows, its Phase 1 ports, or the elements at its held lines -> a Phase 2 choice;
     L3 "extra concept": no reference entry anywhere in the concept's reach -> a Phase 1 choice (or no reference asset).
  R3 did the diagram walk bring the element in: for every scored primary (TP and FP), "anchored" when Phase 1's entry
     already points at it (its enters/leaves-through ports, or an element occurring at the concept's held lines),
     else "walk-found"; precision of each class. Also by how its points were reached ("holding block" / arrow / none)
     and by the point's block kind in the diagram ([process], [logic], [inst], [generate], an output-port assignment).
  R4 the 3-of-3 FPs by shape key (fp_v9h.shape) with the reference entries of the same shape, and by the v9h groups
     G1-G9 (which survived the v9i bars; which are new).
  R5 Phase 1 size: concepts per module and run, concepts with no correct primary, "considered, not kept" counts.
Self-test: per module and run, the FP count equals listed - correct of compare_v8.score, and the per-run listed /
correct sums over the held-out 26 and the tuning 15 equal read_v9j.json's J1 rows.

  python -B fp_v9j.py
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

os.environ["FP_VERSION"] = "two_phase_v9j"
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, MODEL, EFFORT  # noqa: E402
import fp_v9h as F  # noqa: E402

V, TR, HR, CH = F.V, F.TR, F.HR, F.CH
VER, REPS = "two_phase_v9j", (0, 1, 2)
GROUPS_FILE = str(HERE / "fp_groups.json")   # the nine v9h false-positive groups (copied from the session scratchpad on 2026-10-19)


def load(m, r, part):
    f = CH.run_dir(VER, MODEL, r, EFFORT) / part / f"{m}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def diagram_blocks(m):
    """point name -> block kind from inputs/v1/<group>/<module>/diagram.txt; output ports -> 'output port'."""
    kinds, units = {}, 0
    for grp in ("tuning", "heldout"):
        f = LAB / "inputs" / "v1" / grp / m / "diagram.txt"
        if f.exists():
            break
    else:
        return {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("UNIT "):
            units += 1
        mo = re.match(r"^\s+\[(\w+)\] (\S+?)(?: (\([^)]*\)))?: ", line)
        if mo:
            kinds.setdefault(mo.group(2), mo.group(1))
            if mo.group(3):
                kinds.setdefault(f"{mo.group(2)} {mo.group(3)}", mo.group(1))
        mo = re.match(r"^\s+OUTPUTS: (.*)$", line)
        if mo:
            for p in mo.group(1).split(", "):
                kinds.setdefault(p.strip(), "output port")
    kinds["__units__"] = units
    return kinds


def occ_lines(m):
    return {x: set(fx.get("occurrence lines") or []) for (e, x), fx in CH.closed_names(m).items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    g, ref = V.R10.CV.groups_and_ref()
    mods = list(g["tuning"]) + list(g["held-out"])
    held = set(g["held-out"])
    groups9 = json.loads(open(GROUPS_FILE, encoding="utf-8").read())["groups"]
    g9 = {fp: x["name"] for x in groups9 for fp in x["fps"]}
    ok, out = True, {"version": VER, "per_module": {}, "occurrences": [], "primaries": []}
    sums = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    fp_runs = defaultdict(set)  # (module, element) -> runs listed as FP
    for m in mods:
        kd, _ = TR.kinds(m)
        refset = set(ref[m])
        occ = occ_lines(m)
        kinds = diagram_blocks(m)
        per_m = {"reference": len(ref[m]), "fp per run": {}, "concepts per run": {}, "not kept per run": {}}
        for r in REPS:
            a, p1, p2 = load(m, r, "assets"), load(m, r, "phase1"), load(m, r, "phase2")
            if a is None:
                continue
            fps = F.fps(m, r, ref[m])
            sc = V.R10.CV.C8.score(VER, r, m, ref)
            if sc is None or len(fps) != sc[0] - sc[1]:
                ok = False
            grp = "held-out 26" if m in held else "tuning 15"
            sums[grp][r][0] += sc[0]
            sums[grp][r][1] += sc[1]
            per_m["fp per run"][f"r{r}"] = len(fps)
            concepts = {c["id"]: c for c in (p1["reply"].get("conceptual assets") or []) if isinstance(c, dict) and c.get("id")}
            per_m["concepts per run"][f"r{r}"] = len(concepts)
            per_m["not kept per run"][f"r{r}"] = len(p1["reply"].get("considered, not kept") or [])
            rows2 = [x for x in (p2["reply"].get("structural assets") or []) if isinstance(x, dict)]
            nrep = [x for x in (p2["reply"].get("not reported") or []) if isinstance(x, dict)]
            pts = {(x.get("concept id"), x.get("point")): x for x in (p2["reply"].get("points") or []) if isinstance(x, dict)}
            # the concept's reach, for L1-L3
            prim_of, reach_of = defaultdict(set), defaultdict(set)
            for x in rows2:
                reach_of[x.get("concept id")].add(x.get("element"))
                if x.get("label") == "primary":
                    prim_of[x.get("concept id")].add(x.get("element"))
            for x in nrep:
                reach_of[x.get("concept id")].add(x.get("element"))
            anchor_of = {}
            for cid, c in concepts.items():
                ports = set(c.get("enters through") or []) | set(c.get("leaves through") or [])
                hl = set(c.get("held lines") or [])
                at_held = {x for x, ls in occ.items() if ls & hl}
                anchor_of[cid] = ports | at_held
                reach_of[cid] |= ports | at_held
            fpleft = Counter(fps)
            for row in a["Assets"]:
                e = row["Asset RTL"]
                cids = [c for c in (row.get("Concepts") or []) if c]
                is_fp = fpleft[e] > 0
                if is_fp:
                    fpleft[e] -= 1
                correct = e in refset and not is_fp
                anchored = any(e in anchor_of.get(c, set()) for c in cids)
                reached = []
                for c in cids:
                    for pt in row.get("Points") or []:
                        x = pts.get((c, pt))
                        if x:
                            reached.append(("holding" if str(x.get("reached by", "")).startswith("holding") else "arrow", kinds.get(pt, "?")))
                how = "none" if not reached else ("holding block" if all(t == "holding" for t, _ in reached) else ("arrow" if all(t == "arrow" for t, _ in reached) else "mixed"))
                bk = sorted({k for _, k in reached})
                out["primaries"].append({"module": m[8:], "run": r, "element": e, "kind": kd.get(e, "?"), "correct": correct, "fp": is_fp,
                                         "anchored": anchored, "reached": how, "block kinds": bk, "concepts": cids})
                if is_fp:
                    lv = []
                    for c in cids:
                        if prim_of[c] & refset:
                            lv.append("L1")
                        elif reach_of[c] & refset:
                            lv.append("L2")
                        else:
                            lv.append("L3")
                    level = "L1" if "L1" in lv else ("L2" if "L2" in lv else "L3")
                    fp_runs[(m[8:], e)].add(r)
                    out["occurrences"].append({"module": m[8:], "run": r, "element": e, "kind": kd.get(e, "?"), "level": level, "levels": lv,
                                               "concepts": cids, "concept names": [concepts.get(c, {}).get("concept") for c in cids],
                                               "anchored": anchored, "reached": how, "block kinds": bk,
                                               "units in diagram": kinds.get("__units__"), "concept unit": [concepts.get(c, {}).get("unit") for c in cids]})
            # concepts with no correct primary
            per_m.setdefault("concepts without a correct primary", {})[f"r{r}"] = sum(1 for c in concepts if not (prim_of[c] & refset))
        out["per_module"][m[8:]] = per_m
    print(f"self-test 1 (per module and run, FP count = listed - correct, compare_v8.score): {'PASS' if ok else 'FAIL'}")
    rj = json.loads((HERE / "read_v9j.json").read_text(encoding="utf-8"))["J1"]
    ok2 = True
    for grp in ("held-out 26", "tuning 15"):
        for i, row in enumerate(rj[grp]["candidate"]["runs"]):
            if [row["listed"], row["correct"]] != sums[grp][i]:
                ok2 = False
    print(f"self-test 2 (listed / correct sums per run equal read_v9j.json J1): {'PASS' if ok2 else 'FAIL'} {dict((k, dict(v)) for k, v in sums.items())}")
    if not (ok and ok2):
        sys.exit(1)
    occs, prims = out["occurrences"], out["primaries"]
    # R1
    stab = Counter(len(v) for v in fp_runs.values())
    occ_by_stab = Counter(len(fp_runs[(o["module"], o["element"])]) for o in occs)
    per_mod_fp = Counter(o["module"] for o in occs)
    top = per_mod_fp.most_common(10)
    R1 = {"FP occurrences (3 runs, 41 modules)": len(occs), "per group and run": {k: {f"r{r}": v[0] - v[1] for r, v in d.items()} for k, d in sums.items()},
          "FP elements by runs listed": {f"{k} of 3": v for k, v in sorted(stab.items())}, "FP occurrences by element stability": {f"{k} of 3": v for k, v in sorted(occ_by_stab.items())},
          "top modules (FP occurrences over 3 runs)": top, "share of occurrences in top 10 modules": round(sum(v for _, v in top) / len(occs), 3)}
    # R2
    lv_all = Counter(o["level"] for o in occs)
    lv_3 = Counter(o["level"] for o in occs if len(fp_runs[(o["module"], o["element"])]) == 3)
    lv_kind = {lv: dict(Counter(o["kind"] for o in occs if o["level"] == lv)) for lv in ("L1", "L2", "L3")}
    R2 = {"occurrences by level": dict(lv_all), "3-of-3 occurrences by level": dict(lv_3), "level by kind": lv_kind,
          "L3 examples (extra concepts)": [f"{o['module']}:{o['element']} <- {o['concept names']}" for o in occs if o["level"] == "L3"][:40]}
    # R3
    def prec(rows):
        c, f = sum(x["correct"] for x in rows), sum(x["fp"] for x in rows)
        return {"correct": c, "fp": f, "precision": round(c / (c + f), 3) if c + f else None}
    R3 = {"anchored": prec([x for x in prims if x["anchored"]]), "walk-found": prec([x for x in prims if not x["anchored"]]),
          "by reached": {k: prec([x for x in prims if x["reached"] == k]) for k in ("holding block", "arrow", "mixed", "none")},
          "by block kind (primaries citing exactly one kind)": {k: prec([x for x in prims if x["block kinds"] == [k]]) for k in sorted({b for x in prims for b in x["block kinds"]})},
          "walk-found by kind": {k: prec([x for x in prims if not x["anchored"] and x["kind"] == k]) for k in ("port", "record port", "port field", "signal", "record signal", "signal field")},
          "anchored by kind": {k: prec([x for x in prims if x["anchored"] and x["kind"] == k]) for k in ("port", "record port", "port field", "signal", "record signal", "signal field")}}
    # R4
    cons = sorted(k for k, v in fp_runs.items() if len(v) == 3)
    key_fp, key_ref = defaultdict(list), defaultdict(list)
    kinds_cache = {}
    for (mm, e) in cons:
        m = "neorv32_" + mm
        if m not in kinds_cache:
            kinds_cache[m] = TR.kinds(m)[0]
        key_fp[F.shape(m, e, kinds_cache[m])["key"]].append(f"{mm}:{e}")
    for m in mods:
        if m not in kinds_cache:
            kinds_cache[m] = TR.kinds(m)[0]
        for n in ref[m]:
            key_ref[F.shape(m, n, kinds_cache[m])["key"]].append(f"{m[8:]}:{n}")
    patterns = [{"shape": k, "fps": len(v), "modules": len({i.split(':')[0] for i in v}), "ref same shape": len(key_ref.get(k, [])), "examples": v[:8], "ref examples": key_ref.get(k, [])[:5]}
                for k, v in sorted(key_fp.items(), key=lambda t: -len(t[1]))]
    separable = [p for p in patterns if p["ref same shape"] == 0]
    gcount = Counter(g9.get(f"{mm}:{e}", "new (not a v9h consistent FP)") for mm, e in cons)
    R4 = {"3-of-3 FP elements": len(cons), "by v9h group": dict(gcount.most_common()), "shapes with no reference entry of the same shape": sum(p["fps"] for p in separable),
          "patterns": patterns[:30], "by kind": dict(Counter(kinds_cache["neorv32_" + mm].get(e, "?") for mm, e in cons))}
    # R5
    R5 = {"concepts per run (41 modules)": [sum(pm["concepts per run"].get(f"r{r}", 0) for pm in out["per_module"].values()) for r in REPS],
          "concepts without a correct primary per run": [sum(pm.get("concepts without a correct primary", {}).get(f"r{r}", 0) for pm in out["per_module"].values()) for r in REPS],
          "considered, not kept per run": [sum(pm["not kept per run"].get(f"r{r}", 0) for pm in out["per_module"].values()) for r in REPS],
          "reference entries (41 modules)": sum(len(ref[m]) for m in mods)}
    out.update({"R1": R1, "R2": R2, "R3": R3, "R4": R4, "R5": R5, "consistent": [f"{mm}:{e}" for mm, e in cons]})
    (HERE / "fp_v9j.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k in ("R1", "R2", "R3", "R4", "R5"):
        d = dict(out[k])
        d.pop("patterns", None)
        d.pop("L3 examples (extra concepts)", None)
        print(k, json.dumps(d, ensure_ascii=False))
    print("R4 patterns (top 20):")
    for p in patterns[:20]:
        print(f"  {p['fps']:3} FPs in {p['modules']:2} modules | ref same shape {p['ref same shape']:3} | {p['shape']} | {p['examples'][:3]}")
    print("R2 L3 examples:", R2["L3 examples (extra concepts)"][:20])


if __name__ == "__main__":
    main()
