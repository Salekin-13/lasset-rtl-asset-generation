"""Write diff_v5g_to_<version>.md: every passage of <version>'s common.md, phase1.md and phase2.md that differs from
two_phase_v5g, as REMOVED / ADDED blocks with the sentence before it (the same format the v6 blind judges used), so a
condensed version can get the same blind boundary test as v6 and the two results can be compared decision by decision.

  python make_diff.py two_phase_v6abc
"""
import difflib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]


def sents(t):
    return [s for s in re.split(r"(?<=[.:;])\s+(?=[\"'(A-Z-])|\n+", t) if s.strip()]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ver = sys.argv[1]
    old_d, new_d = LAB / "prompts" / "two_phase_v5g", LAB / "prompts" / ver
    md = [f"# What {ver} changes against v5g (for the blind judges)", "",
          "Every changed passage per file. REMOVED = v5g text that the new version deletes or replaces; ADDED = new text.",
          "'after:' is the sentence just before the change. Cite changes as 'change <file>#<n>'.", ""]
    n_all = 0
    for f in ("common.md", "phase1.md", "phase2.md"):
        a, b = sents((old_d / f).read_text(encoding="utf-8")), sents((new_d / f).read_text(encoding="utf-8"))
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        md.append(f"## {f}")
        n = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            n += 1
            before = a[i1 - 1].strip() if i1 > 0 else "(start)"
            md.append(f"### change {f}#{n} (after: \"{before[-120:]}\")")
            if i2 > i1:
                md.append("- REMOVED: " + " ".join(s.strip() for s in a[i1:i2]))
            if j2 > j1:
                md.append("- ADDED: " + " ".join(s.strip() for s in b[j1:j2]))
            md.append("")
        n_all += n
    out = HERE / f"diff_v5g_to_{ver.replace('two_phase_', '')}.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"{out.name}: {n_all} changes, {len(' '.join(md).split())} words")


if __name__ == "__main__":
    main()
