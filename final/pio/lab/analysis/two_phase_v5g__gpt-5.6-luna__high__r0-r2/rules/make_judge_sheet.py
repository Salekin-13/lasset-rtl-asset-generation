"""Write rules_for_judges.md: the v6 rule texts the blind boundary judges apply, one section per rule id, with the
phase each text belongs to and its kind. Only the prompt texts are shown: the drafters' targets, spares, falsifiers and
reasons are left out, because they name correct finds and false positives (blindness).
Input: selected_rules.json (written by make_v6.py: the rules that go into the build, with their final texts).

  python make_judge_sheet.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rules = json.loads((HERE / "selected_rules.json").read_text(encoding="utf-8"))
    out = ["# v6 rule texts for the blind boundary test", "",
           "Each rule is new or sharpened prompt text. 'Phase 1 text' goes into the Phase 1 prompt (it decides which",
           "conceptual assets are kept and which RTL lines they cite); 'Phase 2 text' into the Phase 2 prompt (it decides",
           "which elements are primary). A 'replace' edit replaces older text, quoted as 'replaces'.", ""]
    for r in rules:
        out.append(f"## {r['id']} ({r['kind']})")
        for e in r["edits"]:
            ph = {"phase1.md": "Phase 1 text", "phase2.md": "Phase 2 text", "common.md": "Text read by both phases"}[e["file"]]
            out.append(f"- **{ph}** ({e['mode']}):")
            if e["mode"] == "replace":
                out.append(f"  - replaces: {e['anchor']}")
            out.append(f"  - {e['text'].strip()}")
        out.append("")
    (HERE / "rules_for_judges.md").write_text("\n".join(out), encoding="utf-8")
    print(f"rules_for_judges.md: {len(rules)} rules, {sum(len(r['edits']) for r in rules)} texts")


if __name__ == "__main__":
    main()
