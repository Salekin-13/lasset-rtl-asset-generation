"""Blind views for the boundary test of Phase 2 fixes on two_phase_v5f's stored replies (r0-r2, 15 modules).

views_blind/<short>.md: per run, per concept walk, the concept (name, information, objectives, anchors) and every
Phase 2 asset row with a row id, its label, Functionality, Justification, Found At and lines. Nothing says which rows
the reference lists, so judges who apply a proposed rule to these rows cannot aim at the answer.
boundary_key.json (hidden from judges): per row id, the element, entity, label, and two code facts:
  "correct if primary": the element is a findable reference name of the module (exact name);
  "counted now": the row's element is a correct find of that run in the scorer file (a listed primary that matched).
Self-test: per run, the number of distinct correct primary names from the key equals compare_v5f.json's correct count.

  python make_blind_views.py
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
LAB = AN.parents[1]
ROOT = LAB.parents[2]
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402

V, MODEL, EFF = "two_phase_v5f", "gpt-5.6-luna", "high"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import eval_assets as ea
    with CH.at_root():
        refs = ea.load_refs()["gt"]
    (HERE / "views_blind").mkdir(exist_ok=True)
    key, per_run_correct = {}, {0: 0, 1: 0, 2: 0}
    for m in CH.tuning_modules():
        short = m.replace("neorv32_", "")
        names = {n for (_, n) in CH.closed_names(m)}
        findable = {n for n, _ in refs[m] if n in names}
        out = [f"# {short}: Phase 2 rows of three runs (blind view; no reference marks)", ""]
        for r in (0, 1, 2):
            run = CH.run_dir(V, MODEL, r, EFF)
            p1 = K.parse_json(json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            p2 = K.parse_json(json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            assets = json.loads((run / "assets" / f"{m}.json").read_text(encoding="utf-8"))["Assets"]
            # correct finds of this run in the scorer file (exact; each listed element used once)
            listed = {}
            for x in assets:
                listed[x["Asset RTL"]] = listed.get(x["Asset RTL"], 0) + 1
            correct = set()
            for n, _ in refs[m]:
                if n in names and listed.get(n, 0) > 0:
                    listed[n] -= 1
                    correct.add(n)
            per_run_correct[r] += sum(1 for n, _ in refs[m] if n in correct)
            concepts = {c.get("Concept ID"): c for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)}
            out.append(f"## Run r{r}")
            for w in p2.get("Concept Walks", []):
                if not isinstance(w, dict):
                    continue
                cid = w.get("Concept ID")
                c = concepts.get(cid, {})
                out.append(f"### r{r}:{cid} {c.get('Concept Name')}")
                out.append(f"- information: {c.get('Information')}")
                out.append(f"- objectives at risk: {', '.join(c.get('Objectives At Risk') or [])}; enters through: "
                           f"{', '.join(c.get('Enters Through') or []) or '-'}; leaves through: {', '.join(c.get('Leaves Through') or []) or '-'}")
                if w.get("No Primary Reason"):
                    out.append(f"- no primary reason: {w['No Primary Reason']}")
                for i, a in enumerate(w.get("Assets") or [], 1):
                    if not isinstance(a, dict):
                        continue
                    rid = f"{short}:r{r}:{cid}:{i}"
                    el, lab = a.get("Asset RTL"), a.get("Label")
                    same = [x for x in (a.get("Same Role") or []) if isinstance(x, str)]
                    sec = "; ".join(f"{l.get('Primary RTL')} ({l.get('Direction')})" for l in (a.get("Secondary To") or []) if isinstance(l, dict))
                    out.append(f"- [{rid}] {el} ({a.get('Entity')}) | {lab}" + (f" | same role: {', '.join(same)}" if same else "")
                               + (f" | secondary to: {sec}" if sec else "") + f" | found at: {', '.join(a.get('Found At') or []) or '-'}"
                               + f" | lines {a.get('Asset Lines')}")
                    out.append(f"    functionality: {a.get('Functionality')}")
                    out.append(f"    justification: {a.get('Justification')}")
                    els = [el] + same
                    key[rid] = {"module": m, "run": r, "concept": cid, "elements": els, "entity": a.get("Entity"), "label": lab,
                                "correct if primary": [e for e in els if e in findable],
                                "counted now": [e for e in els if lab == "primary" and e in correct]}
                for x in w.get("Not Reported") or []:
                    if isinstance(x, dict):
                        out.append(f"- not reported: {x.get('Element RTL')} ({x.get('Element Entity')}): {x.get('Why Not Reported')}")
            out.append("")
        (HERE / "views_blind" / f"{short}.md").write_text("\n".join(out), encoding="utf-8")
    (HERE / "boundary_key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    cmp = json.loads((AN / "compare_v5f.json").read_text(encoding="utf-8"))["B"]["runs"]["v5f"]
    ok = all(per_run_correct[r] == cmp[r]["correct"] for r in (0, 1, 2))
    print(f"rows {len(key)}; correct per run from the scorer files {per_run_correct}; compare_v5f.json "
          f"{[cmp[r]['correct'] for r in (0, 1, 2)]}; self-test {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
