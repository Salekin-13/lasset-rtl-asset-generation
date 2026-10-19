"""two_phase_v9m = two_phase_v9l with the LOCATED input: Phase 2's user message gets, per concept, the closed-set elements the Phase 1
entry locates (chain.located: Enters / Leaves Through ports, and every element assigned at one of the entry's held lines), and the
step 4 precedence refers to that list instead of to "held lines" the model reads itself. User 2026-10-18: "Build the per-concept
located list as a Phase 2 input (two_phase_v9m, inputs v1 plus the list), make the precedence refer to it". Phase 1, common.md and
phase1_user.md stay byte-identical to v9j / v9l.
Self-test: for two_phase_v9j r0 on all 41 modules, "the element is in LOCATED of one of its concepts" equals the strict anchoring
of fp_v9j_detail (assignment lines x held lines, or an Enters / Leaves Through port) for every scored primary row, up to the
name-collision rows the verifier of D87 found (same-named elements in different entities); the count of disagreements is printed
and must be below ten.

  python -B make_v9m.py [--write]
"""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
os.environ.setdefault("PIO_INPUT_VERSION", "v1")
sys.path.insert(0, str(LAB / "analysis" / "prompt_builds" / "v10"))
sys.path.insert(0, str(HERE))
import make_v10 as M  # noqa: E402
import fp_v9j_detail as FD  # noqa: E402

CK, CH = M.CK, M.CH
SRC, DST = "two_phase_v9l", "two_phase_v9m"
OLD_PREC = ("read with this precedence: (1) where its value is stored or computed in this unit at a held line of its CONCEPTS entry (a held line "
            "whose statement assigns a whole record assigns each field it writes); (2) where it crosses the unit's boundary whole; (3) for a "
            "decision or setting, the element that holds or makes it at such a held line. An element that stores, re-times, selects or computes "
            "the value only at lines the entry does not cite as held lines, however the walk reached it, is a path to the primary (2.7: a copy "
            "kept while the value moves, a stage, a derived flag or result), not a primary, unless a sentence or block below labels it primary; "
            "it can be a secondary with its direction.")
NEW_PREC = ("read with this precedence: (1) where its value is stored or computed in this unit, when LOCATED names the element for this "
            "conceptual asset; (2) where it crosses the unit's boundary whole; (3) for a decision or setting, the element that holds or makes it, "
            "when LOCATED names it. An element LOCATED does not name for this conceptual asset, wherever it stores, re-times, selects or computes "
            "the value and however the walk reached it, is a path to the primary (2.7: a copy kept while the value moves, a stage, a derived flag "
            "or result), not a primary, unless a sentence or block below labels it primary; it can be a secondary with its direction. LOCATED is "
            "fixed for this call: read it as written and add nothing to it, even where a held line seems to assign the element.")
OLD_HEAD_END = "\n\nSteps, for each conceptual asset in CONCEPTS:"
NEW_HEAD = ("\n\nA second input, LOCATED: for each Concept ID, the closed-set elements its entry locates (the ports in its Enters Through and Leaves "
            "Through, and every element assigned at one of its Held Lines), built by a program from CONCEPTS and the closed set. Step 4 reads it as "
            "written." + OLD_HEAD_END)
OLD_USER = "=== CONCEPTS (the \"Conceptual Assets\" list of Phase 1; fixed) ===\n{concepts}\n"
NEW_USER = (OLD_USER + "\n=== LOCATED (built by a program from CONCEPTS and the closed set: for each Concept ID, the elements its entry locates; fixed) ===\n"
            "{located}\n")


def selftest():
    g, ref = FD.V.R10.CV.groups_and_ref()
    mods = list(g["tuning"]) + list(g["held-out"])
    agree = disagree = 0
    bad = []
    for m in mods:
        a, p1 = FD.J.load(m, 0, "assets"), FD.J.load(m, 0, "phase1")
        if a is None:
            continue
        al = FD.assign_lines(m)
        concepts = {c["id"]: c for c in (p1["reply"].get("conceptual assets") or []) if isinstance(c, dict) and c.get("id")}
        L = CH.located(m, CH.concepts_as_written(p1, "two_phase_v9j"))
        for row in a["Assets"]:
            e = row["Asset RTL"]
            cids = row.get("Concepts") or []
            strict = any(e in set(concepts.get(c, {}).get("enters through") or []) | set(concepts.get(c, {}).get("leaves through") or [])
                         or (al.get(e, set()) & set(concepts.get(c, {}).get("held lines") or [])) for c in cids)
            inl = any(e in L.get(str(c), []) for c in cids)
            if strict == inl:
                agree += 1
            else:
                disagree += 1
                bad.append(f"{m[8:]}:{e} strict={strict} located={inl}")
    print(f"self-test: LOCATED membership vs strict anchoring on v9j r0 primaries: agree {agree}, disagree {disagree} {bad[:8]}")
    return disagree < 10


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    if not selftest():
        sys.exit("self-test FAIL")
    body = (LAB / "prompts" / SRC / "phase2.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    user = (LAB / "prompts" / SRC / "phase2_user.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert body.count(OLD_PREC) == 1 and body.count(OLD_HEAD_END) == 1 and user.count(OLD_USER) == 1
    new_body = body.replace(OLD_PREC, NEW_PREC).replace(OLD_HEAD_END, NEW_HEAD)
    new_user = user.replace(OLD_USER, NEW_USER)
    print(f"precedence {len(OLD_PREC.split())} -> {len(NEW_PREC.split())} words; header +{len(NEW_HEAD.split()) - len(OLD_HEAD_END.split())} words; phase2.md words {len(body.split())} -> {len(new_body.split())}")
    if not write:
        return
    crlf = b"\r\n" in (LAB / "prompts" / SRC / "phase2.md").read_bytes()
    d = LAB / "prompts" / DST
    d.mkdir(exist_ok=True)
    for f in ("common.md", "phase1.md", "phase1_user.md"):
        shutil.copyfile(LAB / "prompts" / SRC / f, d / f)
    (d / "phase2.md").write_bytes((new_body.replace("\n", "\r\n") if crlf else new_body).encode("utf-8"))
    (d / "phase2_user.md").write_bytes((new_user.replace("\n", "\r\n") if crlf else new_user).encode("utf-8"))
    (d / "README.md").write_text("# two_phase_v9m: v9l + the LOCATED input (per concept, the elements the Phase 1 entry locates, built by chain.located from the "
                                 "closed set) with the step 4 precedence referring to it; Phase 1 unchanged (built 2026-10-18; analysis/v10_diagnosis/make_v9m.py; "
                                 "PLAN_ISOLATE_CLUSTER_ORDER.md section 18)\n", encoding="utf-8")
    chk = bool(CK.check(DST, log=print))
    nf = CH.new_format(DST, 1) and CH.new_format(DST, 2)
    same = all((LAB / "prompts" / "two_phase_v9j" / f).read_bytes() == (d / f).read_bytes() for f in ("common.md", "phase1.md", "phase1_user.md"))
    # the user message builds with the LOCATED slot filled from a stored Phase 1 reply
    rec = json.loads((CH.run_dir("two_phase_v9j", "gpt-5.6-luna", 0, "high") / "phase1" / "neorv32_slink.json").read_text(encoding="utf-8"))
    um = CH.user_message(DST, 2, "neorv32_slink", CH.concepts_as_written(rec, "two_phase_v9j"))
    slot = "=== LOCATED" in um and '"C1": [' in um and "{located}" not in um
    sha1, sha2 = M.sha(CK.system(DST, 1))[:12], M.sha(CK.system(DST, 2))[:12]
    print(f"checker {chk}; new_format {nf}; common.md, phase1.md, phase1_user.md identical to v9j {same}; LOCATED slot fills {slot}; sha12 {sha1} / {sha2} (v9l {M.sha(CK.system(SRC, 1))[:12]} / {M.sha(CK.system(SRC, 2))[:12]})")
    ok = chk and nf and same and slot and sha1 == M.sha(CK.system(SRC, 1))[:12]
    print("ALL CHECKS PASS" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
