"""The wording fix for the debug bar's port exception (user 2026-10-19: "fix the wording problem"; D99: the debug module's reset-request
output was lost in every position because the bar removes the concept of the register that drives it, and the port goes with the
concept). Fix: the Phase 1 copy now says that what the halt-request and reset-request outputs deliver stays a piece of its own, held at
the port (2.6: the output port returning it), even where the only register driving the port is barred; the barred register goes under
Not Kept, the port under Leaves Through. The Phase 2 copy says those output ports are primary for what they deliver even where the
driving register is barred. Built on A = two_phase_v9n_place with the Phase 1 copy FIRST (the Tier 1 winner) and the Phase 2 copy as
the last bar before the keep blocks (as in two_phase_v9n_place_dbg): two_phase_p1o_first2. Its run waits for the Tier 3 result (user).
  python -B make_p1_fix.py [--write]
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(HERE))
import make_v10 as M  # noqa: E402
import make_v9n as MN  # noqa: E402

CK, CH = M.CK, M.CH
SRC, DST = "two_phase_v9n_place", "two_phase_p1o_first2"
OLD_OUT1 = ("  Outcome: it only holds or decides what the debug ports deliver: not a piece of its own, although step 2, step 3, Held outcomes, 2.4, 4.2 and 4.4 "
            "would keep it: keep no concept for it, name it in no concept's information, and cite no line assigning it as a held line. The spared elements "
            "and the unit's ports are judged as usual: keep their concepts and their labels (user decision 2026-10-19: reference convention).")
NEW_OUT1 = ("  Outcome: it only holds or decides what the debug ports deliver: not a piece of its own, although step 2, step 3, Held outcomes, 2.4, 4.2 and 4.4 "
            "would keep it: keep no concept for it, name it in no concept's information, and cite no line assigning it as a held line. What the halt-request "
            "and reset-request outputs deliver stays a piece of its own, held at the port (2.6: the output port returning it) even where the only register "
            "driving the port is barred: keep that concept, list the port under Leaves Through, cite the port's assignment line as its held line, and put the "
            "barred register under Not Kept, never the port. The other spared elements and the unit's inputs are judged as usual: keep their concepts and "
            "their labels (user decision 2026-10-19: reference convention).")
OLD_OUT2 = ("  Outcome: it never qualifies as primary for any conceptual asset, although 2.6's storage and decision clauses and examples, this step's "
            "decision-or-setting clause and its one-place sentence would make it primary; it can be a secondary (2.7) of the port or register the operation "
            "targets (user decision 2026-10-19: reference convention).")
NEW_OUT2 = ("  Outcome: it never qualifies as primary for any conceptual asset, although 2.6's storage and decision clauses and examples, this step's "
            "decision-or-setting clause and its one-place sentence would make it primary; it can be a secondary (2.7) of the port or register the operation "
            "targets. The halt-request and reset-request output ports are primary for what they deliver (2.6: the output port returning it), even where "
            "the only register driving them is barred: label the port primary and the register, if listed at all, secondary to it "
            "(user decision 2026-10-19: reference convention).")
TITLE_RE = re.compile(r"^- [A-Z][^\n]*?\.(\s|$)")
FIRST_KEEP = "- Control record ports."


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    l1, l2 = MN.AD_P1.split(chr(10)), MN.AD_P2.split(chr(10))
    assert l1[-1].startswith("  Outcome:") and l2[-1].startswith("  Outcome:"), "the bar texts in make_v9n.py changed shape; re-anchor the fix"
    print(f"replacing Outcome lines ({len(l1[-1].split())} and {len(l2[-1].split())} words) with the fixed ones ({len(NEW_OUT1.split())} and {len(NEW_OUT2.split())})")
    p1_bar, p2_bar = chr(10).join(l1[:-1] + [NEW_OUT1]), chr(10).join(l2[:-1] + [NEW_OUT2])
    a1 = (LAB / "prompts" / SRC / "phase1.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    a2 = (LAB / "prompts" / SRC / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = a1.split("\n")
    t = [i for i, l in enumerate(lines) if TITLE_RE.match(l)]
    assert len(t) == 46
    defs = [i for i in t if lines[i].startswith(("- Describe", "- Precedence", "- Reading a rule"))]
    ins = max(defs) + 1
    n1 = "\n".join(lines[:ins] + p1_bar.split("\n") + lines[ins:])
    j4, j5 = a2.index("\n4. Primary."), a2.index("\n5. Secondary.")
    s4 = a2[j4:j5]
    assert s4.count("\n" + FIRST_KEEP) == 1 and "- Debug module registers." not in a2
    kk = s4.index("\n" + FIRST_KEEP)
    n2 = a2[:j4] + s4[:kk].rstrip("\n") + "\n" + p2_bar + s4[kk:] + a2[j5:]
    print(f"Phase 1 bar {len(MN.AD_P1.split())} -> {len(p1_bar.split())} words at line {ins + 1}; Phase 2 bar {len(MN.AD_P2.split())} -> {len(p2_bar.split())} words")
    if not write:
        return
    crlf = b"\r\n" in (LAB / "prompts" / SRC / "phase1.md").read_bytes()
    d = LAB / "prompts" / DST
    d.mkdir(exist_ok=True)
    for f in ("common.md", "phase1_user.md", "phase2_user.md"):
        shutil.copyfile(LAB / "prompts" / SRC / f, d / f)
    (d / "phase1.md").write_bytes((n1.replace("\n", "\r\n") if crlf else n1).encode("utf-8"))
    (d / "phase2.md").write_bytes((n2.replace("\n", "\r\n") if crlf else n2).encode("utf-8"))
    (d / "README.md").write_text(f"# {DST}: A + the debug-register bar with the fixed port wording (halt and reset request outputs keep their own concept and primary label), Phase 1 copy FIRST, Phase 2 copy last bar before the keep blocks (built 2026-10-19; make_p1_fix.py; PLAN_P1_ORDER.md section 10; run waits for the Tier 3 result)\n", encoding="utf-8")
    chk = bool(CK.check(DST, log=lambda *a: None))
    print(f"{DST}: checker {chk}; sha12 {M.sha(CK.system(DST, 1))[:12]} / {M.sha(CK.system(DST, 2))[:12]}")
    print("ALL CHECKS PASS" if chk else "CHECKS FAILED")
    if not chk:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
