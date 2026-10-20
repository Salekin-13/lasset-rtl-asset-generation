"""two_phase_v9l = two_phase_v9j with the precedence written into the CORE sentence of Phase 2 step 4 (no separate bar): "stored or
computed" counts only at a held line of the Phase 1 entry, "crosses the boundary whole" as before, a decision or setting at such a
held line; an element storing or computing the value only at lines the entry does not cite is a path (2.7), unless a sentence or
block below labels it primary. User 2026-10-18: "Build two_phase_v9l with the precedence written into step 4's core sentence
(stored or computed counts only at Phase 1's held lines and at the boundary; elsewhere on the walk the element is a path), remove
the separate bar". Built from v9j (which has no such bar). Phase 1, common.md and the user templates stay byte-identical.

  python -B make_v9l.py [--write]
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(HERE))
import make_v10 as M  # noqa: E402

CK, CH = M.CK, M.CH
SRC, DST = "two_phase_v9j", "two_phase_v9l"
OLD = ("4. Primary. Among the structural assets of step 3, label primary each element that 2.6 makes primary for this conceptual asset: "
       "where its value is stored or computed in this unit, where it crosses the unit's boundary whole, or, for a decision or setting, "
       "the element that holds or makes it. Outside a coprocessor, sequencing state (below) is not such a decision or setting.")
NEW = ("4. Primary. Among the structural assets of step 3, label primary each element that 2.6 makes primary for this conceptual asset, "
       "read with this precedence: (1) where its value is stored or computed in this unit at a held line of its CONCEPTS entry (a held line "
       "whose statement assigns a whole record assigns each field it writes); (2) where it crosses the unit's boundary whole; (3) for a "
       "decision or setting, the element that holds or makes it at such a held line. An element that stores, re-times, selects or computes "
       "the value only at lines the entry does not cite as held lines, however the walk reached it, is a path to the primary (2.7: a copy "
       "kept while the value moves, a stage, a derived flag or result), not a primary, unless a sentence or block below labels it primary; "
       "it can be a secondary with its direction. Outside a coprocessor, sequencing state (below) is not such a decision or setting.")


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    body = (LAB / "prompts" / SRC / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert body.count(OLD) == 1, f"core sentence occurs {body.count(OLD)} times in {SRC}/phase2.md"
    assert "- Walk-found internals." not in body, "v9j must not carry the separate bar"
    new_body = body.replace(OLD, NEW)
    print(f"core sentence replaced: {len(OLD.split())} -> {len(NEW.split())} words; phase2.md words {len(body.split())} -> {len(new_body.split())}")
    if not write:
        return
    crlf = b"\r\n" in (LAB / "prompts" / SRC / "phase2.md").read_bytes()
    d = LAB / "prompts" / DST
    d.mkdir(exist_ok=True)
    for f in ("common.md", "phase1.md", "phase1_user.md", "phase2_user.md"):
        shutil.copyfile(LAB / "prompts" / SRC / f, d / f)
    (d / "phase2.md").write_bytes((new_body.replace("\n", "\r\n") if crlf else new_body).encode("utf-8"))
    (d / "README.md").write_text("# two_phase_v9l: v9j with the primary precedence written into Phase 2 step 4's core sentence (stored or computed counts at the "
                                 "entry's held lines; elsewhere on the walk the element is a path); no separate bar; Phase 1 unchanged (built 2026-10-18; "
                                 "analysis/v10_diagnosis/make_v9l.py; PLAN_ISOLATE_CLUSTER_ORDER.md section 17)\n", encoding="utf-8")
    chk = bool(CK.check(DST, log=print))
    nf = CH.new_format(DST, 1) and CH.new_format(DST, 2)
    same = all((LAB / "prompts" / SRC / f).read_bytes() == (d / f).read_bytes() for f in ("common.md", "phase1.md", "phase1_user.md", "phase2_user.md"))
    sha1, sha2 = M.sha(CK.system(DST, 1))[:12], M.sha(CK.system(DST, 2))[:12]
    j1, j2 = M.sha(CK.system(SRC, 1))[:12], M.sha(CK.system(SRC, 2))[:12]
    print(f"checker {chk}; new_format {nf}; common.md, phase1.md and user templates identical to v9j {same}; sha12 {sha1} / {sha2} (v9j {j1} / {j2})")
    ok = chk and nf and same and sha1 == j1 and sha2 != j2
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
