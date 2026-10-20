"""v11r3 = v11r2 with the cause readers' minimal rewordings applied to the failing wordings (user 2026-10-17: "Apply the
cause readers' minimal rewordings to the failing wordings (Pacing pulses P1/P2, Port buffers P1/P2, Operation selectors
P1/P2, Sequencing state P1), check them with blind Claude judges, then plan a luna re-test ...").

Sources: v11r2_verify.json (workflow wf_f1cf60e1-a26). Port buffers and Operation selectors: the old -> new pairs of the
reader's try_edits.py, copied verbatim. Pacing pulses and Sequencing state: each finding's phrase -> its "Replace with"
text (proposals.json A-M). J (the count-enable clarification) is in proposals.json without a finding of its own; it is
applied and marked so. Unchanged: Access command fields (passed) and Sequencing state P2 (passed), byte-equal to v11r2.
Every edit must match exactly once in its text; the checkers must pass. Writes new_rules/rule_texts_v11r3.json.

  python -B make_v11r3.py
"""
import json
import os
import sys

os.environ.setdefault("PIO_INPUT_VERSION", "v1")
from diag_common import HERE, register  # noqa: E402

register()
import check_new_rules as CN  # noqa: E402

mt = CN.mt
PB = [  # Port buffers, Phase 1 (try_edits.py)
    ("strobes; and, in a FIFO pushed or popped by another unit's accesses on this unit's input bus request record port (2.6), its fill flags", "strobes, its fill flags"),
    ("a command read only by such lines,", "a command read only by such clear lines,"),
    ("bits shifted in from a serial input port).\n  Exceptions:", "bits shifted in from a serial input port); for all but its push and pop strobes, also: a push or pop strobe of it is decoded from a field of an input bus request record port (2.6).\n  Exceptions:"),
    ("(a record port's field so wired stays covered)", "(a record port's field that is itself the strobe stays covered)"),
    ("Scope: that FIFO (random bits).", "Scope: only a FIFO whose write data the unit generates rather than receives at a port (random bits)."),
]
PB2 = [
    ("strobes; and, in a FIFO pushed or popped by another unit's accesses on this unit's input bus request record port, its fill flags", "strobes, its fill flags"),
    ("a command read only by such lines,", "a command read only by such clear lines,"),
    ("bits shifted in from a serial input port).\n  Exceptions:", "bits shifted in from a serial input port); for all but its push and pop strobes, also: a push or pop strobe of it is decoded from a field of an input bus request record port (2.6).\n  Exceptions:"),
    ("(a record port's field so wired stays covered)", "(a record port's field that is itself the strobe stays covered)"),
]
OS1 = [  # Operation selectors, Phase 1 (try_edits.py)
    ("a processor issues, even one passing others on (a processor", "a processor issues to it (a processor"),
    ("(3) flags decoded from them only naming the operation.\n", "(3) flags decoded from them only naming the operation. A flag whose assignment reads more than these fields (a start or valid signal, a state) does not only name the operation.\n"),
    ("a start command or pulse other than these fields,", "a start command or pulse that is not a field of an input record port,"),
    (", even one copying a criterion (3) flag, which stays covered;", ", even one copying a criterion (3) flag;"),
    ("a setting decoded from them changing", "a setting decoded from them (not a copy) changing"),
    ("(2) Not covered: the whole record port; a plain", "(2) Not covered: a plain"),
]
OS2 = [
    ("a processor issues, even one passing others on (a processor", "a processor issues to it (a processor"),
    ("a start command or pulse other than these fields,", "a start command or pulse that is not a field of an input record port,"),
    (", even one copying a criterion (3) flag, which stays covered;", ", even one copying a criterion (3) flag;"),
    ("(2) Not covered: the whole record port; a plain", "(2) Not covered: a plain"),
]
PP_BOTH = [  # Pacing pulses, both phases (findings A, H, G, B, E, F1, F2, I; J from proposals.json only)
    ("including a done, write or pop strobe set under a test of such a tick or pulse",
     "including a done, write or pop strobe set inside a test of a tick or edge pulse this unit makes, or a wire copying such a strobe"),
    ("a start pulse, or its wire or one-register copy (not a register chain), decoded from a received command or access",
     "a start pulse or an access's read, write or pop strobe, or its wire or one-register copy (not a register chain), decoded from a received command or access"),
    ("(not a count, its copy or a bit of either)", "(never a count, a count's copy, or a bit of one)"),
    ("or delayed by a register chain", "or the strobe at the end of a register chain (registers in series, not one register; not the chain's earlier stages)"),
    ("a pulse a count adds as an operand (2.2)", "a pulse that is a term of a count's sum (2.2: explicit flow; a pulse only tested before an increment is a condition, still covered)"),
    ("A carry computed from a count stays covered.", "The carry bit out of a count's own sum stays covered."),
    ("a count whose compare with a limit raises a reset, error or interrupt, or sets an output level",
     "a count whose compare with a limit raises a reset, error or interrupt, or sets an output level, and that compare's flag"),
    ("a step counter (sequencing state, below, judges it)",
     "a bit, word or step counter that restarts with each transfer or operation, not only when disabled or at its own limit (sequencing state, below, judges it)"),
    ("an enable deciding whether the count runs at all", "an enable deciding whether the count runs at all (not a tick letting it advance one step)"),  # J
]
PP_P1 = [  # Pacing pulses, Phase 1 only (findings C, D)
    ("an input port or a field of one, used only as a condition",
     "an input port or a field of one, used only as a condition (2.2: at the end of that path it is only tested, never combined into a value by a logic or arithmetic operator)"),
    ("or the input port bringing that pulse", "or the input port whose value is that added pulse"),
]
SS_P1 = [  # Sequencing state, Phase 1 only (findings K, L, M)
    ("Outcome: a step counter, one piece of information with that state.", "Outcome: a step counter: information of its own, one piece with that state."),
    ("a test or debug access port a peer's clock paces (say which, from its ports and entity)",
     "a test or debug access port with a clock input port a peer drives, besides the unit's own clock (say which, from its ports and entity)"),
    ("phase counter (even a divider count reloaded each bit)", "phase counter (even a divider count reloaded at each bit of a transfer)"),
]
EDITS = {("P1-14", "P1"): PB, ("P1-14", "P2"): PB2, ("P1-22", "P1"): OS1, ("P1-22", "P2"): OS2,
         ("P1-04", "P1"): PP_BOTH + PP_P1, ("P1-04", "P2"): PP_BOTH, ("P1-15", "P1"): SS_P1}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    T = json.loads((HERE / "new_rules" / "rule_texts_v11r2.json").read_text(encoding="utf-8"))
    bad = mt.check_prompt("- X.\n  Scope: at most 20 elements.\n  Criteria: y.\n  Outcome: z.", CN.names(), "P1-14")["problems"]
    print("self-test (checker flags a planted numeric hint):", "PASS" if bad else "FAIL")
    if not bad:
        sys.exit(1)
    out = {rid: dict(v) for rid, v in T.items()}
    ok = True
    for (rid, ph), edits in EDITS.items():
        t = T[rid][ph]
        for old, new in edits:
            n = t.count(old)
            if n != 1:
                print(f"FAIL: {rid} {ph}: {n} matches for {old[:70]!r}")
                ok = False
                continue
            t = t.replace(old, new)
        p1, p2 = CN.check_text(rid, ph, t), mt.check_prompt(t, CN.names(), rid)["problems"]
        ok &= not p1 and not p2
        print(f"{rid} {ph}: {len(edits)} edits; words {len(T[rid][ph].split())} -> {len(t.split())}; check_text {p1}; check_prompt {p2}")
        out[rid][ph] = t
    same = [(r, ph) for r in T for ph in ("P1", "P2") if (r, ph) not in EDITS]
    ok &= all(out[r][ph] == T[r][ph] for r, ph in same)
    print("unchanged wordings byte-equal to v11r2:", same)
    if not ok:
        sys.exit("FAIL; nothing written")
    (HERE / "new_rules" / "rule_texts_v11r3.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("written new_rules/rule_texts_v11r3.json")


if __name__ == "__main__":
    main()
