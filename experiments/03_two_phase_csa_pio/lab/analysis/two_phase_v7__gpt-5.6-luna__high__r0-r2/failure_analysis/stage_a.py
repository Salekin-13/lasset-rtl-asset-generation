"""Stage A (code): the step 2 funnel facts a line or a key decides, the false-positive listings, the correct finds,
and one pack per module for the stage B concept judges, with the pack completeness check.

Funnel facts (step 2), per reference element missed in a run (not found by the exact scorer), and per kept concept of
that run (stage B decides which concepts match the element's reference concept; B2 then stops at the first failing step):
  (b) lines: the concept's Held, Entry or Exit Lines include one of the element's closed-set occurrence lines, or its
      Enters Through / Leaves Through names the element, its port (for a port field), or a field of it (for a port);
  (c) walk: the concept's Phase 2 walk visits a point where the element appears: a diagram block whose member list has
      the element (or its record base), or the element's own unit port;
  (d) naming: an asset row of that walk names the element ("Asset RTL" or "Same Role"), any label;
  (e) label: that row is primary; if secondary, its Justification is quoted.
  Also kept: Not Kept rows naming the element (with Merged Into / Why Not Kept), Not Reported rows, No Primary Reason
  texts naming it, and every Phase 2 row in any walk naming it.
False-positive listings: per run, the listed primaries no reference entry consumed (common_fa.fp_listings), with the
  concepts that list them, their walk rows, and the element's closed-set role.
Correct finds: per run, every found reference entry, with its closed-set "role in RTL" set and its home RC id (for
  the same-shape lists of stage B2).

Self-tests against hand-read lines (run first; nothing is written if one fails):
  - raw copies equal the stored "raw" fields byte for byte;
  - wdt RTL line 94 reads "ctrl.enable  <= bus_req_i.data(ctrl_enable_c);" and ctrl.enable's occurrence lines hold 94;
  - wdt diagram: ctrl.enable is a member of block bus_access, at diagram.txt line 7 (hand-read);
  - v7 r0 wdt phase 1, concept C1 "Watchdog enable setting": Held Lines [75, 94] (hand-read from the stored reply);
  - v7 r0 wdt phase 2, walk C1 row 'ctrl.enable' is primary, found at bus_access;
  - the missed element-runs counted here equal 327 - correct found (per run, from compare_v7.runs);
  - the false-positive listings counted here equal listed - correct (per run).

  python stage_a.py
"""
import json
import sys
from collections import defaultdict

import common_fa as F

CH = F.CH
PACKS = F.HERE / "packs" / "module"


def concept_anchor_hit(c, name, port):
    hits = []
    for key in ("Enters Through", "Leaves Through"):
        for a in CH.as_list(c.get(key)):
            if not isinstance(a, str):
                continue
            if a == name or (port and a == port) or a.split(".")[0] == name:
                hits.append(f"{key}: {a}")
    return hits


def walk_facts(w, lm_walk, name, at):
    """Facts of one walk for one element. at: {point: (diagram line, why)} where the element appears."""
    if w is None:
        return {"walk": None}
    pts = [p.get("Point") for p in (w.get("Points") or []) if isinstance(p, dict)]
    reached = [{"point": p, "diagram line": at[p][0], "why": at[p][1]} for p in pts if p in at]
    rows = []
    for i, a in enumerate(w.get("Assets") or []):
        if not isinstance(a, dict):
            continue
        if a.get("Asset RTL") == name or name in (a.get("Same Role") or []):
            rows.append({"label": a.get("Label"), "entity": a.get("Entity"), "found at": a.get("Found At"),
                         "justification": a.get("Justification"), "functionality": a.get("Functionality"),
                         "raw line": lm_walk["assets"][i] if lm_walk and i < len(lm_walk["assets"]) else None,
                         "via same role": a.get("Asset RTL") != name})
    nr = []
    for i, x in enumerate(w.get("Not Reported") or []):
        if isinstance(x, dict) and x.get("Element RTL") == name:
            nr.append({"why": x.get("Why Not Reported"), "raw line": lm_walk["not reported"][i] if lm_walk and i < len(lm_walk["not reported"]) else None})
    npr = w.get("No Primary Reason")
    return {"walk": lm_walk["line"] if lm_walk else None, "points": pts, "reached points holding it": reached,
            "rows naming it": rows, "not reported": nr,
            "no primary reason naming it": npr if npr and F.has_name(name, npr) else None}


def stop_if_matched(cf):
    """The first failing step if this concept were the element's matched concept."""
    if not (cf["cites lines"] or cf["cites port"]):
        return "b"
    wf = cf["walk"]
    if wf.get("walk") is None or not wf["reached points holding it"]:
        return "c"
    if not wf["rows naming it"]:
        return "d"
    if not any(r["label"] == "primary" for r in wf["rows naming it"]):
        return "e"
    return "passes a-e"


def selftests():
    out = []
    n, ok = F.extract_raw()
    out.append((f"raw copies equal the stored 'raw' fields ({n} files)", ok))
    rl = F.rtl_file_lines("neorv32_wdt")
    out.append(("wdt RTL line 94 text", rl[94][1].strip() == "ctrl.enable  <= bus_req_i.data(ctrl_enable_c);"))
    out.append(("wdt ctrl.enable occurrence lines hold 94", 94 in F.element_lines("neorv32_wdt", "ctrl.enable")))
    at = F.points_with_element("neorv32_wdt", "ctrl.enable")
    out.append(("wdt ctrl.enable member of bus_access at diagram line 7", at.get("bus_access", (None,))[0] == 7))
    p1 = F.parsed(0, "neorv32_wdt", 1)
    c1 = next(c for c in p1["Conceptual Assets"] if c["Concept ID"] == "C1")
    out.append(("v7 r0 wdt C1 Held Lines [75, 94]", c1["Concept Name"] == "Watchdog enable setting" and c1["Held Lines"] == [75, 94]))
    p2 = F.parsed(0, "neorv32_wdt", 2)
    w1 = next(w for w in p2["Concept Walks"] if w["Concept ID"] == "C1")
    row = next(a for a in w1["Assets"] if a["Asset RTL"] == "ctrl.enable")
    out.append(("v7 r0 wdt walk C1 ctrl.enable primary at bus_access", row["Label"] == "primary" and row["Found At"] == ["bus_access"]))
    lm = F.line_maps(0, "neorv32_wdt")
    L1 = F.raw_path(0, "neorv32_wdt", 1).read_text(encoding="utf-8").splitlines()
    out.append(("line map: wdt r0 C1 line holds its Concept ID", '"Concept ID": "C1"' in L1[lm["phase1"]["C1"] - 1]))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    st = selftests()
    for lab, v in st:
        print(f"  {'ok  ' if v else 'FAIL'} {lab}")
    if not all(v for _, v in st):
        sys.exit("self-test failed: nothing written")
    runs = F.C7.runs(F.VERSION, F.REPS)
    misses, fps, correct = [], [], {}
    lmaps = {}
    for r in F.REPS:
        for m in F.MODS:
            lmaps[(r, m)] = F.line_maps(r, m)       # raises if a line cannot be found or checked
    for m in F.MODS:
        s = F.short(m)
        ents = F.ref_entries(m)
        rl = F.rtl_file_lines(m)
        for r in F.REPS:
            l, t, found, _ = F.CC.score(F.VERSION, r, m)
            p1, p2 = F.parsed(r, m, 1), F.parsed(r, m, 2)
            lm = lmaps[(r, m)]
            cons = [c for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)]
            walks = {w.get("Concept ID"): w for w in p2.get("Concept Walks", []) if isinstance(w, dict)}
            for key, name, k, home in ents:
                roles = F.element_roles(m, name)
                if key in found:
                    correct.setdefault(key, {"module": s, "element": name, "k": k, "home RC": home, "runs": [],
                                             "role in RTL": {e: list(v) for e, v in roles.items()},
                                             "signature": F.BP.role_signature(F.module(m).facts(F.module(m).entities_of(name)[0], name)) if F.module(m).entities_of(name) else None})
                    correct[key]["runs"].append(f"r{r}")
                    continue
                lines = F.element_lines(m, name)
                port = F.element_port(m, name)
                at = F.points_with_element(m, name)
                per_c = {}
                for c in cons:
                    cid = c.get("Concept ID")
                    cl = set(CH.as_list(c.get("Held Lines"))) | set(CH.as_list(c.get("Entry Lines"))) | set(CH.as_list(c.get("Exit Lines")))
                    cf = {"name": c.get("Concept Name"), "raw line": lm["phase1"].get(cid),
                          "cites lines": sorted(x for x in cl if isinstance(x, int) and x in lines),
                          "cites port": concept_anchor_hit(c, name, port),
                          "walk": walk_facts(walks.get(cid), lm["phase2"].get(cid), name, at)}
                    cf["stop if matched"] = stop_if_matched(cf)
                    per_c[cid] = cf
                nk = []
                for i, x in enumerate(p1.get("Not Kept", []) or []):
                    if isinstance(x, dict) and F.has_name(name, json.dumps(x, ensure_ascii=False)):
                        nk.append({"candidate": x.get("Candidate Name"), "merged into": x.get("Merged Into"),
                                   "why not kept": x.get("Why Not Kept"), "raw line": lm["not kept"][i]})
                misses.append({"item": f"M:{key}:r{r}", "key": key, "module": s, "element": name, "k": k, "run": f"r{r}",
                               "home RC": home, "role in RTL": {e: list(v) for e, v in roles.items()},
                               "port": port, "element lines": lines,
                               "rtl": [f"RTL {x} (rtl.txt line {rl[x][0]}): {rl[x][1].strip()}" for x in lines if x in rl],
                               "diagram points holding it": {p: {"diagram line": v[0], "why": v[1]} for p, v in at.items()},
                               "arrows carrying it": [f"diagram.txt line {i}: {a}" for i, a in F.arrows_with_element(m, name)],
                               "not kept naming it": nk, "per concept": per_c,
                               "concepts naming it in any row": sorted(cid for cid, cf in per_c.items() if cf["walk"].get("rows naming it"))})
            # false positives
            for x in F.fp_listings(r, m):
                name, ent = x["element"], x["entity"]
                M = F.module(m)
                fx = M.facts(ent, name)
                rows = []
                for cid in x["concepts"]:
                    w = walks.get(cid)
                    if not w:
                        continue
                    wf = walk_facts(w, lm["phase2"].get(cid), name, F.points_with_element(m, name))
                    c = next((c for c in cons if c.get("Concept ID") == cid), {})
                    rows.append({"concept": cid, "concept name": c.get("Concept Name"), "concept raw line": lm["phase1"].get(cid),
                                 "walk raw line": wf["walk"], "points": wf["points"], "rows": wf["rows naming it"]})
                fps.append({"item": f"F:{s}:{ent}:{name}:r{r}", "module": s, "element": name, "entity": ent, "run": f"r{r}",
                            "concepts": x["concepts"], "role in RTL": list((CH.closed_names(m).get((ent, name)) or {}).get("role in RTL") or []),
                            "signature": F.BP.role_signature(fx), "listing": rows,
                            "rtl": [f"RTL {y} (rtl.txt line {rl[y][0]}): {rl[y][1].strip()}" for y in (fx["lines"] if fx else [])[:8] if y in rl]})
    # count checks against the scorer
    ok = True
    for r in F.REPS:
        nm = sum(1 for x in misses if x["run"] == f"r{r}")
        nf = sum(1 for x in fps if x["run"] == f"r{r}")
        c1 = nm == 109 - runs[r]["correct"]
        c2 = nf == runs[r]["listed"] - runs[r]["correct"]
        print(f"  {'ok  ' if c1 and c2 else 'FAIL'} r{r}: missed element-runs {nm} = 109 - {runs[r]['correct']}; false-positive listings {nf} = {runs[r]['listed']} - {runs[r]['correct']}")
        ok &= c1 and c2
    if not ok:
        sys.exit("count check failed: nothing written")
    # frequency class per element (misses) and per (module, entity, element) (false positives)
    nmiss = defaultdict(int)
    for x in misses:
        nmiss[x["key"]] += 1
    nfp = defaultdict(int)
    for x in fps:
        nfp[(x["module"], x["entity"], x["element"])] += 1
    cls = {3: "consistent (3 of 3 runs)", 2: "frequent (2 of 3)", 1: "intermittent (1 of 3)"}
    for x in misses:
        x["class"] = cls[nmiss[x["key"]]]
    for x in fps:
        x["class"] = cls[nfp[(x["module"], x["entity"], x["element"])]]
    (F.HERE / "funnel_facts.json").write_text(json.dumps(misses, indent=1, ensure_ascii=False), encoding="utf-8")
    (F.HERE / "fp_listings.json").write_text(json.dumps(fps, indent=1, ensure_ascii=False), encoding="utf-8")
    (F.HERE / "correct_finds.json").write_text(json.dumps(correct, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"missed element-runs {len(misses)} ({len(nmiss)} elements); false-positive listings {len(fps)} ({len(nfp)} distinct); "
          f"correct finds {sum(len(v['runs']) for v in correct.values())} element-runs ({len(correct)} elements)")
    from collections import Counter
    print("misses by class:", dict(Counter(x["class"] for x in misses)), "| false positives by class:", dict(Counter(x["class"] for x in fps)))
    write_module_packs(lmaps)


# ------------------------------------------------------------------------------------------- module packs ---
def write_module_packs(lmaps):
    """packs/module/ref_<short>.md and runs_<short>.md: the stage B judges' views (same content as the v5g views, plus
    file:line for every row). Completeness check: every part of every item is present, or written as 'none: <reason>'."""
    PACKS.mkdir(parents=True, exist_ok=True)
    gt_json = json.loads((F.ROOT / "data" / "ground_truth" / "manual_gt_neorv32.json").read_text(encoding="utf-8"))["modules"]
    problems, n_items = [], 0
    for m in F.MODS:
        s = F.short(m)
        # reference side
        v = [f"# Reference for {m}", "", f"Source: reference rows from data/ground_truth/manual_gt_neorv32.json; reference concepts from "
             f"{F.rel(F.REFCONCEPTS)} (line of each concept's id given).", "", "Reference rows (the ground truth lists structural assets only):", ""]
        seen = []
        for a in gt_json[m]["assets"]:
            if (a["raw_cell"], a["why"]) not in seen:
                seen.append((a["raw_cell"], a["why"]))
                v.append(f"- {a['raw_cell']} | objectives {', '.join(a['objectives'])} | why: {a['why']}")
        v += ["", "Reference conceptual assets (derived earlier from the 'why' texts by two blind readers and a reconciler):", ""]
        for c in F.REFC[m]:
            n_items += 1
            parts = {"name": c.get("name"), "information": c.get("information"), "kind": c.get("kind"), "where": c.get("where"),
                     "influences": c.get("influences"), "objectives": ", ".join(c.get("objectives") or []),
                     "home elements": ", ".join(c.get("home_elements") or []), "all linked": ", ".join(c.get("elements") or []),
                     "source line": F.refc_line(m, c["id"])}
            for k, x in parts.items():
                if not x:
                    problems.append(f"{s} {c['id']}: {k} missing")
            v += [f"## {c['id']}: {parts['name']}  ({F.rel(F.REFCONCEPTS)}:{parts['source line']})",
                  f"- information: {parts['information']}",
                  f"- kind: {parts['kind']}; where: {parts['where']}; objectives: {parts['objectives']}",
                  f"- influences: {parts['influences']}",
                  f"- structural assets (home): {parts['home elements']}; all linked: {parts['all linked']}", ""]
        (PACKS / f"ref_{s}.md").write_text("\n".join(v), encoding="utf-8")
        # runs side
        v = [f"# Three runs of gpt-5.6-luna on {m} (prompt two_phase_v7, same inputs)", "",
             "File references: the model's replies, copied byte for byte, are in "
             f"{F.rel(F.RAW)}/r<k>/phase1/{m}.json (concepts, Not Kept) and .../phase2/{m}.json (walks).", ""]
        for r in F.REPS:
            p1, p2 = F.parsed(r, m, 1), F.parsed(r, m, 2)
            lm = lmaps[(r, m)]
            listed = F.assets(r, m)
            _, _, found, _ = F.CC.score(F.VERSION, r, m)
            found_names = {k.split(":", 1)[1].split("#")[0] for k in found}
            f1, f2 = F.rel(F.raw_path(r, m, 1)), F.rel(F.raw_path(r, m, 2))
            v += [f"## Run r{r}", ""]
            walks = {w.get("Concept ID"): w for w in p2.get("Concept Walks", []) if isinstance(w, dict)}
            cons = [c for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)]
            for c in cons:
                n_items += 1
                cid = c.get("Concept ID")
                w = walks.get(cid)
                rows = [a for a in ((w or {}).get("Assets") or []) if isinstance(a, dict)]
                prim = [a.get("Asset RTL") + (f" ({a.get('Entity')})" if a.get("Entity") != m else "") for a in rows if a.get("Label") == "primary"]
                sec = [a.get("Asset RTL") + (f" ({a.get('Entity')})" if a.get("Entity") != m else "") for a in rows if a.get("Label") == "secondary"]
                y_all = sum(1 for x in listed if cid in x.get("Concepts", []))
                y_tp = sum(1 for x in listed if cid in x.get("Concepts", []) and x["Asset RTL"] in found_names)
                obj = c.get("Objectives At Risk")
                parts = {
                    "name": c.get("Concept Name"), "unit": c.get("Unit"), "information": c.get("Information"),
                    "objectives": ", ".join(obj) if obj else "none: the reply gives no 'Objectives At Risk' for this concept",
                    "enters through": ", ".join(CH.as_list(c.get("Enters Through"))) or "none: empty in the reply",
                    "leaves through": ", ".join(CH.as_list(c.get("Leaves Through"))) or "none: empty in the reply",
                    "lines": f"entry {c.get('Entry Lines')}; held {c.get('Held Lines')}; exit {c.get('Exit Lines')}",
                    "concept line": f"{f1}:{lm['phase1'].get(cid)}",
                    "walk line": f"{f2}:{lm['phase2'][cid]['line']}" if cid in lm["phase2"] else "none: Phase 2 wrote no walk for it",
                    "primary": ", ".join(prim) or "-", "secondary": ", ".join(sec) or "-",
                }
                for k, x in parts.items():
                    if not x:
                        problems.append(f"{s} r{r} {cid}: {k} missing")
                v += [f"### r{r}:{cid} {parts['name']}  (unit {parts['unit']}; {parts['concept line']}; walk {parts['walk line']})",
                      f"- information: {parts['information']}",
                      f"- objectives: {parts['objectives']}; enters through: {parts['enters through']}; leaves through: {parts['leaves through']}",
                      f"- {parts['lines']}",
                      f"- Phase 2 primary: {parts['primary']}",
                      f"- Phase 2 secondary: {parts['secondary']}",
                      f"- primaries listed under it: {y_all}, of which in the reference: {y_tp}", ""]
            nk = [x for x in (p1.get("Not Kept", []) or [])]
            v.append(f"### r{r}: considered, not kept")
            if not nk:
                v.append("- none: the reply's Not Kept list is empty")
            for i, x in enumerate(nk):
                n_items += 1
                if not isinstance(x, dict) or not x.get("Candidate Name"):
                    problems.append(f"{s} r{r} not kept #{i + 1}: no name")
                    continue
                why = (f"merged into {x.get('Merged Into')}" if x.get("Merged Into") else "") + \
                      ((" | " if x.get("Merged Into") else "") + str(x.get("Why Not Kept")) if x.get("Why Not Kept") else "")
                if not why:
                    problems.append(f"{s} r{r} not kept {x.get('Candidate Name')}: no reason")
                v.append(f"- {x.get('Candidate Name')} ({f1}:{lm['not kept'][i]}): {why or 'none: the reply gives no reason'}")
            v.append("")
            if len(cons) != sum(1 for l in v if l.startswith(f"### r{r}:C") or (l.startswith(f"### r{r}:") and "not kept" not in l)):
                problems.append(f"{s} r{r}: concept count in the pack differs from the reply")
        (PACKS / f"runs_{s}.md").write_text("\n".join(v), encoding="utf-8")
    print(f"module packs: {len(F.MODS)} modules, {n_items} items; completeness check: " + ("PASS" if not problems else f"FAIL {problems}"))
    (F.HERE / "packs" / "module_pack_check.json").write_text(json.dumps({"items": n_items, "problems": problems}, indent=1), encoding="utf-8")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
