"""Blind concept views of two_phase_v7's stored Phase 1 replies (r0-r2), for the stage E blind check of Phase 1 fixes.
Copied from analysis/two_phase_v5g__gpt-5.6-luna__high__r0-r2/boundary/make_blind_concepts.py; changed: the version
(two_phase_v7), the output folder (views/ here, files <short>_concepts.md), the header line ("(blind view)"), and the
self-test (v5g's pack3.json does not exist for v7: the concept counts per run are checked against the counts stage A
read from the replies, stageB/args.json, and against two hand-read counts: hwspinlock r0 has 2 kept concepts, C1 and C2,
and bus r1 has 23).

views/<short>_concepts.md: per run, every kept concept (id, name, information, objectives, rubric answers, anchors,
entry/held/exit lines) with the names of its Phase 2 primary and secondary elements, and the Not Kept list. Nothing says
which elements or concepts the reference lists.

  python make_blind_concepts.py
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FA = HERE.parent
LAB = HERE.parents[3]
sys.path.insert(0, str(LAB))
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
import chain as CH  # noqa: E402
import labkit as K  # noqa: E402

V = "two_phase_v7"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    counts = json.loads((FA / "stageB" / "args.json").read_text(encoding="utf-8"))["modules"]
    (HERE / "views").mkdir(exist_ok=True)
    ok = len(counts["hwspinlock"]["runs"]["r0"]) == 2 and len(counts["bus"]["runs"]["r1"]) == 23
    for m in CH.tuning_modules():
        short = m.replace("neorv32_", "")
        out = [f"# {short}: Phase 1 concepts of three runs with their Phase 2 elements (blind view)", ""]
        for r in (0, 1, 2):
            run = CH.run_dir(V, "gpt-5.6-luna", r, "high")
            p1 = K.parse_json(json.loads((run / "phase1" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            p2 = K.parse_json(json.loads((run / "phase2" / f"{m}.json").read_text(encoding="utf-8"))["raw"])
            walks = {w.get("Concept ID"): w for w in p2.get("Concept Walks", []) if isinstance(w, dict)}
            cs = [c for c in p1.get("Conceptual Assets", []) if isinstance(c, dict)]
            ok &= [c.get("Concept ID") for c in cs] == counts[short]["runs"][f"r{r}"]
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
        (HERE / "views" / f"{short}_concepts.md").write_text("\n".join(out), encoding="utf-8")
    print("self-test (concept ids per run = stage A's reading of the replies; hwspinlock r0 2 and bus r1 23 hand-read):", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
