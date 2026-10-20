"""two_phase_v12 = v11h with the rule fixes that passed their luna rule-alone tests, plus N12 (user 2026-10-17: "Plan the
next Phase 1 candidate from v11h with Access command fields (v11r2), Port buffers P1 (v11r3), Sequencing state (v11r3 P1
+ v11r2 P2) and N12, keeping v11h's Pacing pulses and Operation selectors; give readings and the cost of one full r0 run
before any calls."). Builds the prompt folder only; sends nothing. Plan: PLAN_V12.md.

Changes against v11h (every replaced block must occur exactly once):
  phase1.md  Access command fields (a)+(b)  -> new_rules/rule_texts_v11r2.json P1-23 P1
             Port buffers (a)-(c)           -> new_rules/rule_texts_v11r3.json P1-14 P1
             Sequencing state               -> new_rules/rule_texts_v11r3.json P1-15 P1
             + Command bit copies (N12)     -> new_rules/rule_texts_v11q.json N12 P1, inserted after "Second copies"
  phase2.md  Access command fields block    -> v11r2 P1-23 P2
             Sequencing state block         -> v11r2 P1-15 P2 without its last two sentences (they are v11h's in-place
                                               step-4 sentences, which stay where they are in v11h)
             + Command bit copies (N12)     -> N12 P2, inserted after the "Second copies" block
  Unchanged: Pacing pulses, Operation selectors, Port buffers' Phase 2 block, every other rule, common.md, the user
  templates.

  python -B make_v12.py            (self-test only)
  python -B make_v12.py --write
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, LAB, register  # noqa: E402

register()
import stages as S  # noqa: E402
import check_new_rules as CN  # noqa: E402
import v11 as V  # noqa: E402

BASE, NEW = "two_phase_v11h", "two_phase_v12"
CUR = json.loads((HERE / "new_rules" / "v11h_rule_blocks.json").read_text(encoding="utf-8"))
R2 = json.loads((HERE / "new_rules" / "rule_texts_v11r2.json").read_text(encoding="utf-8"))
R3 = json.loads((HERE / "new_rules" / "rule_texts_v11r3.json").read_text(encoding="utf-8"))
N12 = json.loads((HERE / "new_rules" / "rule_texts_v11q.json").read_text(encoding="utf-8"))["N12"]
INPLACE = ["Outside a coprocessor, sequencing state (below) is not such a decision or setting.",
           "Label a port that step 3 names as setting a state machine's state primary for the conceptual asset about that "
           "state; the state register keeps its own label, and the synchronizer stages defined below stay barred."]


def text(v, f):
    return (LAB / "prompts" / v / f).read_text(encoding="utf-8").replace("\r\n", "\n")


def seq_p2_old(p2):
    """v11h's Phase 2 Sequencing state block: stages.rule_text('P1-15') up to its two in-place sentences."""
    t = S.rule_text("P1-15")
    cut = t.index("\n" + INPLACE[0])
    blk = t[:cut + 1]
    assert p2.count(blk) == 1, "v11h phase2 Sequencing block not found once"
    return blk


def seq_p2_new():
    t = R2["P1-15"]["P2"]
    cut = t.index("\n" + INPLACE[0])
    assert t[cut + 1:] == "\n".join(INPLACE), "v11r2 P2 tail is not the two in-place sentences"
    return t[:cut + 1]


def build():
    p1, p2 = text(BASE, "phase1.md"), text(BASE, "phase2.md")
    reps1 = [(CUR["P1-23 P1"], R2["P1-23"]["P1"]), (CUR["P1-14 P1"], R3["P1-14"]["P1"]), (CUR["P1-15 P1"], R3["P1-15"]["P1"])]
    for old, new in reps1:
        assert p1.count(old) == 1, old[:60]
        p1 = p1.replace(old, new)
    sc1 = p1.index("- Second copies.")
    nx1 = p1.index("\n- Bus handshake copies (a).", sc1)
    p1 = p1[:nx1 + 1] + N12["P1"] + "\n" + p1[nx1 + 1:]
    old_acf2 = S.rule_text("P1-23")
    assert p2.count(old_acf2) == 1
    p2 = p2.replace(old_acf2, R2["P1-23"]["P2"])
    p2 = p2.replace(seq_p2_old(p2), seq_p2_new())
    sc2 = p2.index("- Second copies.")
    nx2 = p2.index("\n- Working values (a).", sc2)
    p2 = p2[:nx2 + 1] + N12["P2"] + "\n" + p2[nx2 + 1:]
    return p1, p2


def selftest(log=print):
    c = {}
    p1, p2 = build()
    b1, b2 = text(BASE, "phase1.md"), text(BASE, "phase2.md")
    c["Pacing pulses and Operation selectors blocks unchanged (both phases)"] = all(
        x in p1 for x in (CUR["P1-04 P1"], CUR["P1-22 P1"])) and all(S.rule_text(r) in p2 for r in ("P1-04", "P1-22"))
    c["Port buffers Phase 2 block unchanged"] = S.rule_text("P1-14") in p2
    c["new blocks present once"] = all(p1.count(t) == 1 for t in (R2["P1-23"]["P1"], R3["P1-14"]["P1"], R3["P1-15"]["P1"], N12["P1"])) and all(
        p2.count(t) == 1 for t in (R2["P1-23"]["P2"], seq_p2_new(), N12["P2"]))
    c["old blocks gone"] = all(p1.count(CUR[k]) == 0 for k in ("P1-23 P1", "P1-14 P1", "P1-15 P1")) and p2.count(S.rule_text("P1-23")) == 0
    c["the two in-place Sequencing sentences stay once in phase 2"] = all(p2.count(s) == 1 for s in INPLACE)
    rest1 = b1
    for k in ("P1-23 P1", "P1-14 P1", "P1-15 P1"):
        rest1 = rest1.replace(CUR[k], "")
    new_rest1 = p1
    for t in (R2["P1-23"]["P1"], R3["P1-14"]["P1"], R3["P1-15"]["P1"], N12["P1"] + "\n"):
        new_rest1 = new_rest1.replace(t, "", 1)
    c["phase 1: everything else byte-equal to v11h"] = rest1 == new_rest1
    rest2 = b2.replace(S.rule_text("P1-23"), "").replace(seq_p2_old(b2), "")
    new_rest2 = p2.replace(R2["P1-23"]["P2"], "", 1).replace(seq_p2_new(), "", 1).replace(N12["P2"] + "\n", "", 1)
    c["phase 2: everything else byte-equal to v11h"] = rest2 == new_rest2
    c["all inserted texts pass check_new_rules"] = all(not CN.check_text(r, ph, t) for r, ph, t in (
        ("P1-23", "P1", R2["P1-23"]["P1"]), ("P1-23", "P2", R2["P1-23"]["P2"]), ("P1-14", "P1", R3["P1-14"]["P1"]),
        ("P1-15", "P1", R3["P1-15"]["P1"]), ("P1-15", "P2", R2["P1-15"]["P2"]), ("N12", "P1", N12["P1"]), ("N12", "P2", N12["P2"])))
    bad = [k for k, ok in c.items() if not ok]
    log(f"make_v12 self-test ({len(c)} checks): {'PASS' if not bad else 'FAIL ' + str(bad)}")
    log(f"words: phase 1 {len(b1.split())} -> {len(p1.split())}; phase 2 {len(b2.split())} -> {len(p2.split())}")
    return not bad


README = """# two_phase_v12: v11h + the rule fixes that passed alone + N12 (built 2026-10-17, not run)

Diagnostic candidate for the next Phase 1 version. Plan, readings and cost: analysis/v10_diagnosis/PLAN_V12.md. Built by
analysis/v10_diagnosis/make_v12.py from two_phase_v11h (v10 + F1 + F2, v10's Phase 2).

- Access command fields, both phases: new_rules/rule_texts_v11r2.json (luna rule-alone PASS, D67). Basis: principle
  (drafter), partly following the reference.
- Port buffers, Phase 1 only: rule_texts_v11r3.json (PASS over its re-test cells, D69). Phase 2 keeps v11h's block.
  Basis: partly a reference convention (user decision under D11 needed before adoption).
- Sequencing state: Phase 1 rule_texts_v11r3.json (0.100, contradictions in 2 modules, D69); Phase 2 v11r2 (PASS, D67).
- Command bit copies (N12), both phases: rule_texts_v11q.json; user decision D66, labelled "user decision: reference
  convention" (D11), partly principle (2.6 carrier sentence).
- Pacing pulses and Operation selectors: unchanged from v11h (their rewordings failed alone).
"""


def write():
    if not selftest():
        sys.exit("self-test FAIL; nothing written")
    p1, p2 = build()
    V.write_version(NEW, p1, p2, README)
    ok = V.CK.check(NEW, log=lambda *a: None)
    print(f"written prompts/{NEW}; check_lab_prompt {'PASS' if ok else 'FAIL'}; sha12 phase 1 {V.CH.sha12(V.CK.system(NEW, 1))}, phase 2 {V.CH.sha12(V.CK.system(NEW, 2))}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    write() if "--write" in sys.argv else sys.exit(0 if selftest() else 1)
