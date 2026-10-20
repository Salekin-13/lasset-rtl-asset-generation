"""Blind concept views of two_phase_v5g's stored Phase 1 replies (r0-r2), for boundary tests of Phase 1 rules.
views_blind_concepts/<short>.md: per run, every kept concept (id, name, information, objectives, rubric answers,
anchors, entry/held/exit lines) with the names of its Phase 2 primary and secondary elements, and the Not Kept list.
Nothing says which elements or concepts the reference lists. Self-test: the number of concepts per run equals
pack3.json.

  python make_blind_concepts.py
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AN = HERE.parent
LAB = AN.parents[1]
sys.path.insert(0, str(LAB))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402

V = "two_phase_v5g"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pack = json.loads((AN / "pack3.json").read_text(encoding="utf-8"))
    (HERE / "views_blind_concepts").mkdir(exist_ok=True)
    ok = True
    for m in CH.tuning_modules():
        short = m.replace("neorv32_", "")
        out = [f"# {short}: Phase 1 concepts of three runs with their Phase 2 elements (blind view; no reference marks)", ""]
        for r in (0, 1, 2):
            run = CH.run_dir(V, "gpt-5.6-luna", r, "high")
            p1 = K.parse_json(json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            p2 = K.parse_json(json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            walks = {w.get("Concept ID"): w for w in p2.get("Concept Walks", []) if isinstance(w, dict)}
            cs = [c for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)]
            ok &= len(cs) == len(pack["modules"][m]["runs"][f"r{r}"]["concepts"])
            out.append(f"## Run r{r}")
            for c in cs:
                cid = c.get("Concept ID")
                w = walks.get(cid, {})
                rows = [a for a in (w.get("Assets") or []) if isinstance(a, dict)]
                prim = [a.get("Asset RTL") for a in rows if a.get("Label") == "primary"]
                sec = [a.get("Asset RTL") for a in rows if a.get("Label") == "secondary"]
                rub = c.get("Rubric") or {}
                out += [f"### r{r}:{cid} {c.get('Concept Name')} (unit {c.get('Unit')})",
                        f"- information: {c.get('Information')}",
                        f"- objectives at risk: {', '.join(c.get('Objectives At Risk') or [])}; rubric yes: "
                        f"{', '.join(k for k, v in rub.items() if v == 'yes') if isinstance(rub, dict) else rub}",
                        f"- enters through: {', '.join(c.get('Enters Through') or []) or '-'}; leaves through: {', '.join(c.get('Leaves Through') or []) or '-'}",
                        f"- entry lines {c.get('Entry Lines')}; held lines {c.get('Held Lines')}; exit lines {c.get('Exit Lines')}",
                        f"- Phase 2 primary: {', '.join(map(str, prim)) or '-'}",
                        f"- Phase 2 secondary: {', '.join(map(str, sec)) or '-'}"]
            nk = [x for x in p1.get("Not Kept", []) if isinstance(x, dict)]
            if nk:
                out.append(f"### r{r}: not kept")
                out += [f"- {x.get('Candidate Name')} ({x.get('Candidate Unit')}): " + (f"merged into {x.get('Merged Into')}" if x.get("Merged Into") else str(x.get("Why Not Kept"))) for x in nk]
            out.append("")
        (HERE / "views_blind_concepts" / f"{short}.md").write_text("\n".join(out), encoding="utf-8")
    print("self-test (concepts per run = pack3.json):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
