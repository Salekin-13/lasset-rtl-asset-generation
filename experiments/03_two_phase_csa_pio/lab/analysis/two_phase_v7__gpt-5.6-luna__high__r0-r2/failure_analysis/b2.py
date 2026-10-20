"""Stage B2 (code): finish the step 2 funnel and step 4a with the stage B concept verdicts, form the pattern groups,
and build one evidence pack per group, with the pack completeness check.

Inputs: stage_a.py's funnel_facts.json, fp_listings.json, correct_finds.json; the stage B final verdict per module
(stageB/final_<m>.json when adjudicated, else stageB/judge1_<m>.json, the v5g rule). Each file is compared with the
workflow journal's return value of the agent that wrote it; a mismatch stops the script.

Funnel (step 2), per missed element-run; stop at the first failing step:
  (a) concept: the stage B verdict of the element's home reference concept in that run. "missed: considered, not kept"
      -> stop at (a): "merged away" if a Not Kept row naming the element has a Merged Into, else "dropped under Not
      Kept"; "missed: never a concept" -> stop at (a): "never named". Otherwise (found, found inside a broader concept,
      found split, partly found) the verdict's model_ids are the element's matched concepts.
  (b)-(e): stage_a.py's per-concept facts for each matched concept; the element's step is the furthest step any of
      its matched concepts reaches (order b < c < d < e < passes a-e).
  An element-run that passes (a)-(e) is listed as "other: passes a-e" (it would be a correct find unless the scorer
  consumed its name for another entry).
Groups for Phase 2 errors are split by where the walk placed the primary row: at a point it reached as a holding block,
  or only at points it reached by an arrow (over-walking candidates, step 3).
Step 4a, per false-positive listing: the stage B verdicts of the concepts that list it. Any concept matching a reference
  concept (matches, broader, narrower) -> "Phase 2 error (concept matches a reference concept)"; all concepts without a
  reference counterpart -> "Phase 1 error (extra concept)".
Groups: misses by stop step (a, b, c, d, e, other), false positives by type (Phase 1 error, Phase 2 error). Inside a
  group, items are ordered consistent (3 of 3 runs), frequent (2 of 3), intermittent (1 of 3).
Same-shape correct finds per item: correct finds in any v7 run (correct_finds.json) whose element has the same
  closed-set "role in RTL" set as the item's element (in any entity), or whose home RC id is the item's matched RC id.
Prompt lines per item: code cannot know which sentence the model followed; it ranks the lines of common.md and the
  phase file by word overlap with the model's own reason (Why Not Kept, Justification, Why Not Reported, No Primary
  Reason), rarer words weighing more, and lists the top three as "candidates (word overlap, approximate)".

Self-tests (first): the stage B files equal the journal returns; every missed element-run and every false-positive
listing lands in exactly one group; the hand-read item (wdt r0 C1 ctrl.enable, primary, a correct find) is not in any
group; group sizes add up to 60 misses and 168 false positives.

  python b2.py <workflow run id of stage B>
"""
import glob
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

import common_fa as F

STEP_ORDER = ["b", "c", "d", "e", "passes a-e"]
GROUP_NAMES = {"a": "miss_a_concept", "b": "miss_b_lines", "c": "miss_c_walk", "d": "miss_d_naming", "e": "miss_e_label",
               "other": "miss_other", "P1": "fp_phase1_extra_concept", "P2H": "fp_phase2_at_holding_block", "P2A": "fp_phase2_via_arrow"}
CLS_ORDER = {"consistent (3 of 3 runs)": 0, "frequent (2 of 3)": 1, "intermittent (1 of 3)": 2}
STOP = set("the a an and or of to in on at is it its be by as for that this with from are not no only when which each "
           "one any its their there than then so if but into out other so such has have was were been can may must "
           "line lines rule element elements".split())


def journal(run_id):
    js = glob.glob(os.path.expanduser(f"~/.claude/projects/*/*/subagents/workflows/{run_id}/journal.jsonl"))
    if not js:
        sys.exit(f"no journal for {run_id}")
    label, res = {}, {}
    for l in open(js[0], encoding="utf-8"):
        x = json.loads(l)
        if x.get("type") == "started":
            label[x["agentId"]] = x.get("label")
        elif x.get("type") == "result":
            res[label.get(x["agentId"], x["agentId"])] = x.get("result")
    return res


def strip(x):
    return {k: v for k, v in x.items() if k != "file_written"} if isinstance(x, dict) else x


def stage_b(run_id):
    J = journal(run_id)
    finals, problems = {}, []
    for m in F.MODS:
        s = F.short(m)
        adj = F.HERE / "stageB" / f"final_{s}.json"
        src = adj if adj.exists() else F.HERE / "stageB" / f"judge1_{s}.json"
        lab = (f"adjudicate:{s}" if adj.exists() else f"judge1:{s}")
        if not src.exists():
            problems.append(f"{s}: no stage B file")
            continue
        x = json.loads(src.read_text(encoding="utf-8"))
        jr = J.get(lab + ":rerun") or J.get(lab)
        if decisions(x) != decisions(jr):
            problems.append(f"{s}: {src.name} differs from the journal return of {lab} in a verdict or matched id")
        elif strip(x) != strip(jr):
            TEXT_ONLY.append(f"{s}: {src.name} differs from the journal return only in free text (notes, evidence)")
        finals[s] = x
    return finals, problems


TEXT_ONLY = []


def decisions(x):
    """The fields code reads: per run, each reference concept's verdict and model ids, each model concept's verdict and
    reference ids."""
    if not isinstance(x, dict):
        return None
    return sorted((r["run"], sorted((g["id"], g["verdict"], tuple(g["model_ids"])) for g in r["gt_concepts"]),
                   sorted((c["id"], c["verdict"], tuple(c["gt_ids"])) for c in r["model_concepts"])) for r in x.get("runs", []))


def words(t):
    return [w for w in re.findall(r"[a-z][a-z\-]+", (t or "").lower()) if w not in STOP and len(w) > 2]


class PromptIndex:
    def __init__(self):
        self.lines = []
        for f in ("common.md", "phase1.md", "phase2.md"):
            for i, l in enumerate((F.PROMPTS / f).read_text(encoding="utf-8").splitlines(), 1):
                if len(l.strip()) > 40:
                    self.lines.append((f, i, l.strip(), set(words(l))))
        df = Counter(w for _, _, _, ws in self.lines for w in ws)
        self.idf = {w: math.log(len(self.lines) / n) for w, n in df.items()}

    def top(self, text, files, k=3):
        q = set(words(text))
        if not q:
            return []
        sc = []
        for f, i, l, ws in self.lines:
            if f in files:
                s = sum(self.idf.get(w, 0) for w in q & ws)
                if s > 0:
                    sc.append((s, f, i, l))
        sc.sort(reverse=True)
        return [f"{F.rel(F.PROMPTS / f)}:{i} (score {s:.1f}): {l[:300]}{' ...' if len(l) > 300 else ''}" for s, f, i, l in sc[:k]]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    run_id = sys.argv[1]
    finals, problems = stage_b(run_id)
    print("self-test: stage B files equal the journal returns in every verdict and matched id:", "PASS" if not problems else f"FAIL {problems}", "| text-only differences:", TEXT_ONLY or "none")
    if problems:
        sys.exit(1)
    misses = json.loads((F.HERE / "funnel_facts.json").read_text(encoding="utf-8"))
    fps = json.loads((F.HERE / "fp_listings.json").read_text(encoding="utf-8"))
    correct = json.loads((F.HERE / "correct_finds.json").read_text(encoding="utf-8"))
    PI = PromptIndex()

    def verdict_rc(s, run, rc):
        rr = next(r for r in finals[s]["runs"] if r["run"] == run)
        return next((g for g in rr["gt_concepts"] if g["id"] == rc), None)

    def verdict_mc(s, run, cid):
        rr = next(r for r in finals[s]["runs"] if r["run"] == run)
        return next((g for g in rr["model_concepts"] if g["id"] == cid), None)

    # ---------------- step 2 funnel
    for x in misses:
        x["stage B"] = None
        if x["home RC"] is None:
            x["stop"], x["stop detail"] = "a", "the element has no home reference concept"
            continue
        g = verdict_rc(x["module"], x["run"], x["home RC"])
        x["stage B"] = g
        if g["verdict"].startswith("missed"):
            x["stop"] = "a"
            if g["verdict"] == "missed: never a concept":
                x["stop detail"] = "never named"
            elif any(n.get("merged into") for n in x["not kept naming it"]):
                x["stop detail"] = "merged away"
            else:
                x["stop detail"] = "dropped under Not Kept"
            continue
        ids = [i for i in g["model_ids"] if i in x["per concept"]]
        x["matched concepts"] = ids
        if not ids:
            x["stop"], x["stop detail"] = "a", f"verdict '{g['verdict']}' names no kept concept of this run ({g['model_ids']})"
            continue
        steps = {i: x["per concept"][i]["stop if matched"] for i in ids}
        best = max(steps.values(), key=STEP_ORDER.index)
        x["stop"] = "other" if best == "passes a-e" else best
        x["stop detail"] = f"furthest step over matched concepts {steps}" + (" (reference concept only partly found)" if g["verdict"] == "partly found" else "")
    # ---------------- step 4a
    for x in fps:
        vs = {c: verdict_mc(x["module"], x["run"], c) for c in x["concepts"]}
        x["concept verdicts"] = {c: (v["verdict"], v["gt_ids"]) if v else None for c, v in vs.items()}
        matched = [c for c, v in vs.items() if v and v["verdict"] != "no reference counterpart"]
        x["type"] = "P2" if matched else "P1"
        x["type detail"] = ("Phase 2 error (concept matches a reference concept: " + ", ".join(f"{c}->{vs[c]['gt_ids']}" for c in matched) + ")"
                            + (" ; also listed under an extra concept" if len(matched) < len(vs) else "")) if matched else \
            "Phase 1 error (extra concept: " + ", ".join(x["concepts"]) + ")"
        x["matched RC"] = sorted({g for c in matched for g in vs[c]["gt_ids"]})
        # Phase 2 errors: where the walk placed the primary row. "holding": a Found At point the walk reached as a holding
        # block; "arrow": every Found At point was reached by an arrow (over-walking candidates, step 3)
        if matched:
            p2w = {w.get("Concept ID"): w for w in F.parsed(int(x["run"][1:]), "neorv32_" + x["module"], 2).get("Concept Walks", []) if isinstance(w, dict)}
            kinds = set()
            for cid in x["concepts"]:
                w = p2w.get(cid)
                if not w:
                    continue
                rb = {p.get("Point"): p.get("Reached By", "") for p in w.get("Points") or [] if isinstance(p, dict)}
                for a in w.get("Assets") or []:
                    if isinstance(a, dict) and a.get("Label") == "primary" and (a.get("Asset RTL") == x["element"] or x["element"] in (a.get("Same Role") or [])):
                        for p in a.get("Found At") or []:
                            kinds.add("holding" if "holding" in rb.get(p, "").lower() else "arrow")
            x["p2 place"] = "holding" if "holding" in kinds else "arrow"
            x["type detail"] += ("; found at a holding block" if x["p2 place"] == "holding" else "; every Found At point reached by an arrow")
    # ---------------- groups
    groups = defaultdict(list)
    for x in misses:
        groups[GROUP_NAMES[x["stop"]]].append(x)
    for x in fps:
        groups[GROUP_NAMES[x["type"] if x["type"] == "P1" else ("P2H" if x["p2 place"] == "holding" else "P2A")]].append(x)
    for g in groups.values():
        g.sort(key=lambda x: (CLS_ORDER[x["class"]], x["module"], x.get("key") or x["element"], x["run"]))
    placed = Counter(x["item"] for g in groups.values() for x in g)
    ok = all(v == 1 for v in placed.values()) and len(placed) == len(misses) + len(fps) == 60 + 168 \
        and not any("ctrl.enable" in i and i.startswith("M:wdt") and ":r0" in i for i in placed)
    print("self-test: every item in exactly one group; 60 + 168 items; wdt r0 ctrl.enable (a correct find) in none:", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)
    # ---------------- same-shape correct finds
    def same_shape(module, element, rcs):
        roles = set(map(tuple, F.element_roles("neorv32_" + module, element).values()))
        out = []
        for key, c in correct.items():
            hit_role = any(tuple(v) in roles for v in c["role in RTL"].values()) if roles else False
            hit_rc = c["module"] == module and c["home RC"] in rcs
            if hit_role or hit_rc:
                out.append(f"{key} (runs {','.join(c['runs'])}; " + ("same role in RTL" if hit_role else "") +
                           ("; " if hit_role and hit_rc else "") + (f"same RC {c['home RC']}" if hit_rc else "") + ")")
        return out
    # ---------------- packs
    out_dir = F.HERE / "packs" / "group"
    out_dir.mkdir(parents=True, exist_ok=True)
    lmaps = {(r, m): F.line_maps(r, m) for r in F.REPS for m in F.MODS}
    pack_problems, summary = [], {}
    for gname, items in sorted(groups.items()):
        v = [f"# Evidence pack: group {gname} ({len(items)} items)", "",
             "Items are ordered consistent (3 of 3 runs), then frequent (2 of 3), then intermittent (1 of 3).",
             f"Model replies (byte-for-byte copies): {F.rel(F.RAW)}/r<k>/phase<p>/<module>.json. Inputs: "
             f"{F.rel(F.INPUTS)}/<module>/rtl.txt (lines start with the RTL line number), diagram.txt, closed_set.json. "
             f"Prompt: {F.rel(F.PROMPTS)}/common.md, phase1.md, phase2.md (one paragraph per line).",
             "Each ELEMENT block gives the parts its items share (RTL lines, diagram lines, same-shape correct finds) once; each item "
             "(### heading) then gives its own run's parts.", ""]
        rendered = {}
        for x in items:
            m = "neorv32_" + x["module"]
            r = int(x["run"][1:])
            lm = lmaps[(r, m)]
            f1, f2 = F.rel(F.raw_path(r, m, 1)), F.rel(F.raw_path(r, m, 2))
            p1, p2 = F.parsed(r, m, 1), F.parsed(r, m, 2)
            cons = {c.get("Concept ID"): c for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)}
            walks = {w.get("Concept ID"): w for w in p2.get("Concept Walks", []) if isinstance(w, dict)}
            parts = {}
            is_miss = x["item"].startswith("M:")
            name = x["element"]
            parts["rtl"] = x["rtl"] or ["none: the element has no occurrence line in the closed set"]
            if is_miss:
                concept_ids = x.get("matched concepts") or []
                head = (f"## {x['item']} | {x['class']} | miss stops at ({x['stop']}): {x['stop detail']} | home RC {x['home RC']}")
                sb = x["stage B"]
                parts["stage B"] = [f"verdict for {x['home RC']} in {x['run']}: {sb['verdict']}; model_ids {sb['model_ids']}; missing part: {sb['missing_part'] or '-'}; evidence: {sb['evidence']}"] if sb else ["none: the element has no home reference concept"]
                rcs = [x["home RC"]] if x["home RC"] else []
                nk = [f"{f1}:{n['raw line']}: '{n['candidate']}' " + (f"merged into {n['merged into']}" if n["merged into"] else "") +
                      (f" | why not kept: {n['why not kept']}" if n["why not kept"] else "") for n in x["not kept naming it"]]
                reason_text = " ".join([n.get("why not kept") or "" for n in x["not kept naming it"]] +
                                       [rw.get("justification") or "" for cf in x["per concept"].values() for rw in cf["walk"].get("rows naming it", [])] +
                                       [nr.get("why") or "" for cf in x["per concept"].values() for nr in cf["walk"].get("not reported", [])] +
                                       [cf["walk"].get("no primary reason naming it") or "" for cf in x["per concept"].values()])
                files = {"common.md", "phase1.md"} if x["stop"] in ("a", "b") else {"common.md", "phase2.md"}
            else:
                concept_ids = x["concepts"]
                head = f"## {x['item']} | {x['class']} | {x['type detail']}"
                parts["stage B"] = [f"{c}: {v[0]} {v[1]}" if v else f"{c}: no verdict" for c, v in x["concept verdicts"].items()]
                rcs = x["matched RC"]
                nk = []
                reason_text = " ".join(rw.get("justification") or "" for l in x["listing"] for rw in l["rows"])
                files = {"common.md", "phase1.md"} if x["type"] == "P1" else {"common.md", "phase2.md"}
            parts["phase 1 concepts"] = []
            for cid in concept_ids:
                c = cons.get(cid)
                if not c:
                    continue
                facts = x["per concept"].get(cid) if is_miss else None
                parts["phase 1 concepts"].append(
                    f"{f1}:{lm['phase1'].get(cid)} {cid} '{c.get('Concept Name')}': information: {c.get('Information')} | enters {c.get('Enters Through')} "
                    f"leaves {c.get('Leaves Through')} | entry {c.get('Entry Lines')} held {c.get('Held Lines')} exit {c.get('Exit Lines')}"
                    + (f" | cites the element's lines {facts['cites lines'] or 'no'}; cites its port {facts['cites port'] or 'no'}" if facts else ""))
            if not parts["phase 1 concepts"]:
                parts["phase 1 concepts"] = [f"none: no kept concept matches its reference concept in {x['run']} (the miss stops at (a))"] if is_miss else ["none: no listing concept"]
            parts["not kept"] = nk or ["none: no Not Kept row of this run names the element"]
            parts["phase 2 walks"] = []
            for cid in concept_ids:
                w = walks.get(cid)
                wl = lm["phase2"].get(cid)
                if not w:
                    parts["phase 2 walks"].append(f"{cid}: none: Phase 2 wrote no walk for it")
                    continue
                pts = [f"{p.get('Point')} <- {p.get('Reached By')} (line {wl['points'][i]})" for i, p in enumerate(w.get("Points") or []) if isinstance(p, dict)]
                rows = []
                for i, a in enumerate(w.get("Assets") or []):
                    if isinstance(a, dict) and (a.get("Asset RTL") == name or name in (a.get("Same Role") or [])):
                        rows.append(f"line {wl['assets'][i]}: {a.get('Asset RTL')} ({a.get('Entity')}) {a.get('Label')}; found at {a.get('Found At')}; "
                                    f"functionality: {a.get('Functionality')}; justification: {a.get('Justification')}")
                nrs = [f"line {wl['not reported'][i]}: NOT REPORTED {y.get('Element RTL')}: {y.get('Why Not Reported')}"
                       for i, y in enumerate(w.get("Not Reported") or []) if isinstance(y, dict) and y.get("Element RTL") == name]
                npr = w.get("No Primary Reason")
                parts["phase 2 walks"].append(f"walk {cid} ({f2}:{wl['line']}; the line numbers below are in this file): points: " + "; ".join(pts)
                                              + (" | rows naming the element: " + " || ".join(rows) if rows else " | no asset row names the element")
                                              + (" | " + " || ".join(nrs) if nrs else "")
                                              + (f" | no primary reason (line {wl['npr']}): {npr}" if npr else ""))
            if not parts["phase 2 walks"]:
                parts["phase 2 walks"] = [f"none: the miss stops at (a); no matched concept has a walk"] if is_miss else ["none: no listing concept has a walk"]
            dl = F.diagram_file_lines(m)
            at = F.points_with_element(m, name)
            dlines = [f"{F.rel(F.INPUTS / m / 'diagram.txt')}:{ln}: {dl[ln - 1].strip()[:400]} ({why})" for p, (ln, why) in at.items() if ln]
            dlines += [f"{F.rel(F.INPUTS / m / 'diagram.txt')}:{i}: {a}" for i, a in F.arrows_with_element(m, name)][:8]
            parts["diagram"] = dlines or ["none: the element is in no block member list, port list or arrow of the diagram"]
            parts["prompt lines"] = PI.top(reason_text, files) or [f"none: the model gives no reason text to match (code cannot pick the sentence it followed)"]
            ekey0 = x.get("key") or f"{x['module']}:{x['entity']}:{name}"
            rcs_all = sorted({r for y in items if (y.get("key") or f"{y['module']}:{y['entity']}:{y['element']}") == ekey0
                              for r in ([y["home RC"]] if y["item"].startswith("M:") and y["home RC"] else y.get("matched RC", []))})
            ss = same_shape(x["module"], name, rcs_all)
            parts["same-shape correct finds"] = ss or ["none: no correct find in any v7 run has the same role in RTL or the same RC"]
            x["same-shape correct finds"] = ss
            for k in ("rtl", "stage B", "phase 1 concepts", "not kept", "phase 2 walks", "diagram", "prompt lines", "same-shape correct finds"):
                if not parts.get(k) or any(not str(y).strip() for y in parts[k]):
                    pack_problems.append(f"{gname} {x['item']}: part '{k}' missing")
            ekey = x.get("key") or f"{x['module']}:{x['entity']}:{name}"
            rendered.setdefault(ekey, []).append((x, head, parts, is_miss))
        # one block per element: the parts shared by its runs once, then each item's own parts
        SHARED = (("rtl", "RTL lines"), ("diagram", "diagram lines"), ("same-shape correct finds", "same-shape correct finds (code)"))
        OWN = (("stage B", "stage B concept verdicts"), ("phase 1 concepts", "Phase 1 concept rows"), ("not kept", "Not Kept rows"),
               ("phase 2 walks", "Phase 2 walk rows"), ("prompt lines", "prompt lines: candidates (word overlap with the model's reason, approximate)"))
        for ekey, xs in rendered.items():
            x0, _, p0, is_miss = xs[0]
            for x, _, p, _ in xs[1:]:
                for k, _ in SHARED:
                    if p[k] != p0[k]:
                        pack_problems.append(f"{gname} {x['item']}: shared part '{k}' differs between runs of {ekey}")
            v.append(f"## ELEMENT {ekey} | {x0['class']} | items: {', '.join(x['item'] for x, _, _, _ in xs)}")
            v.append(f"- element: {x0['element']} | module {x0['module']} | role in RTL: {x0['role in RTL']}" + (f" | signature: {x0['signature']}" if not is_miss else ""))
            for k, label in SHARED:
                v.append(f"- {label} (shared by this element's items):")
                v += [f"    - {y}" for y in p0[k]]
            v.append("")
            for x, head, p, _ in xs:
                v.append("#" + head)
                for k, label in OWN:
                    v.append(f"- {label}:")
                    v += [f"    - {y}" for y in p[k]]
                v.append("")
        (out_dir / f"{gname}.md").write_text("\n".join(v), encoding="utf-8")
        summary[gname] = {"items": len(items), "by class": dict(Counter(x["class"] for x in items)),
                          "by run": dict(Counter(x["run"] for x in items)),
                          "distinct": len({(x.get("key") or (x["module"], x["entity"], x["element"])) if True else 0 for x in items})}
    print("group packs:", json.dumps(summary, indent=1))
    print("pack completeness check:", "PASS" if not pack_problems else f"FAIL {pack_problems[:10]}")
    (F.HERE / "packs" / "group_pack_check.json").write_text(json.dumps({"groups": summary, "problems": pack_problems}, indent=1), encoding="utf-8")
    groups_out = {g: [x["item"] for x in items] for g, items in groups.items()}
    (F.HERE / "groups.json").write_text(json.dumps(groups_out, indent=1), encoding="utf-8")
    (F.HERE / "funnel_final.json").write_text(json.dumps(misses, indent=1, ensure_ascii=False), encoding="utf-8")
    (F.HERE / "fp_typed.json").write_text(json.dumps(fps, indent=1, ensure_ascii=False), encoding="utf-8")
    # step 2 table: by step and class (element-runs), and by run
    tab = defaultdict(Counter)
    for x in misses:
        tab[x["stop"]][x["class"]] += 1
        tab[x["stop"]][x["run"]] += 1
    det = Counter((x["stop"], x["stop detail"].split(" (")[0] if x["stop"] == "a" else "") for x in misses)
    print("step 2 funnel (element-runs):", {k: dict(v) for k, v in sorted(tab.items())})
    print("stop details at (a):", {f"{a} {b}": n for (a, b), n in det.items() if a == "a"})
    print("step 4a:", dict(Counter(x["type"] for x in fps)), "| by class:", {t: dict(Counter(x["class"] for x in fps if x["type"] == t)) for t in ("P1", "P2")})
    (F.HERE / "step2_step4a_tables.json").write_text(json.dumps({"step 2 by stop step": {k: dict(v) for k, v in tab.items()},
                                                                 "step 2 (a) details": {f"{a}|{b}": n for (a, b), n in det.items()},
                                                                 "step 4a": {t: dict(Counter(x["class"] for x in fps if x["type"] == t)) for t in ("P1", "P2")}}, indent=1), encoding="utf-8")
    if pack_problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
