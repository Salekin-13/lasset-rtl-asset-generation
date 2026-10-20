"""Edit-level wording diffs for the stage E blind judges, extracted by code from each surviving fix's wording field
(rules/<ID>/revised.json). For each edit: the v7 file and line, the action, the replaced text ("-" lines, for a replace)
and the new text ("+" lines). A line-level diff would repeat whole paragraphs (one prompt paragraph per line).
Self-check: every edit's old text occurs exactly once on its v7 line (fixcheck.apply would refuse it otherwise), and the
fix applies cleanly (fixcheck.check ok)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fixcheck as FC  # noqa: E402

FIXES = ("B1", "R1", "R2", "R3", "R4", "R5", "R6")
parts = []
for fx in FIXES:
    rv = json.loads((HERE.parent / "rules" / fx / "revised.json").read_text(encoding="utf-8"))
    r = FC.check(rv)
    assert r["ok"], (fx, r["problems"])
    out = [f"=== FIX {fx} ==="]
    for e in rv["wording"]["edits"]:
        line = FC.v7_lines(e["file"])[e["line"] - 1] if e["line"] > 0 else ""
        if e["action"] == "replace":
            assert line.count(e["old_text"]) == 1, (fx, e["file"], e["line"])
            out += [f"{e['file']} line {e['line']}: REPLACE", "- " + e["old_text"], "+ " + e["new_text"], ""]
        else:
            out += [f"{e['file']}: INSERT a new line after line {e['line']}", "+ " + e["new_text"], ""]
    (HERE / "diffs" / f"{fx}.diff").write_text("\n".join(out), encoding="utf-8")
    parts.append("\n".join(out))
(HERE / "diffs" / "all_fixes.diff").write_text("\n".join(parts), encoding="utf-8")
print("words in all_fixes.diff:", len("\n".join(parts).split()))
