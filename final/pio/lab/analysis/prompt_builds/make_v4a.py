"""Start prompt version two_phase_v4a = v4's content in v2a's concise wording.

common.md  = two_phase_v2a/common.md (meaning-checked against v2) + v4's bus-record line (C10), word for word, on its own
             line right after the line that makes forwarding wires and read-back words candidate secondaries (2.6).
phase1.md  = two_phase_v4/phase1.md copied here; a writer then shortens it with the same meaning (checked clause by clause
             against v4's phase1.md, analysis/prompt_builds/v4_phase1_clauses.json).
phase2.md, phase1_user.md, phase2_user.md = byte-identical to v4 (and v2).
Asserts every step; run once before the writer (it overwrites phase1.md with v4's).

  python make_v4a.py
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
P = LAB / "prompts"
V2A, V4, V4A = P / "two_phase_v2a", P / "two_phase_v4", P / "two_phase_v4a"
sys.path.insert(0, str(HERE))
import clauses as CL  # noqa: E402
import make_v4 as M4  # noqa: E402


def main():
    V4A.mkdir(exist_ok=True)
    for f in ("phase1.md", "phase2.md", "phase1_user.md", "phase2_user.md"):
        shutil.copyfile(V4 / f, V4A / f)
    lines = (V2A / "common.md").read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("An internal element that only passes the value on between two of these"))
    assert lines[i - 2].startswith("2.6 Primary asset") and lines[i + 1].startswith("Examples: the key register"), (lines[i - 2][:30], lines[i + 1][:30])
    new = lines[: i + 1] + [M4.C10] + lines[i + 1:]
    (V4A / "common.md").write_text("\n".join(new), encoding="utf-8")
    c = (V4A / "common.md").read_text(encoding="utf-8")
    assert c.count(M4.C10) == 1 and c.replace(M4.C10 + "\n", "") == (V2A / "common.md").read_text(encoding="utf-8")
    for f in ("phase2.md", "phase1_user.md", "phase2_user.md"):
        assert (V4A / f).read_bytes() == (V4 / f).read_bytes() == (P / "two_phase_v2" / f).read_bytes(), f
    json.dump({"phase1.md": CL.split_file(V4 / "phase1.md")}, open(HERE / "v4_phase1_clauses.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"two_phase_v4a started: common.md = v2a + C10 at line {i + 2}; phase1.md = v4 copy "
          f"({len((V4 / 'phase1.md').read_text(encoding='utf-8').split())} words, {len(CL.split_file(V4 / 'phase1.md'))} clauses)")


if __name__ == "__main__":
    main()
