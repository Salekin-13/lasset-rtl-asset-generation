"""Overnight candidates (D92; run_v9n.py), all built from two_phase_v9j unless said; Phase 1 identical to v9j except C.
  A two_phase_v9n_place  step 4 core sentence: one primary per place where the information is.
  B two_phase_v9n_conf   A "Confidence" key on each asset row ("sure" / "possible" for primaries, "" for secondaries) with a
                         calibration sentence in step 4; chain.py carries it to the assets file; scored sure-only and all.
  C two_phase_v9n_cfg    Phase 1 bar "Tuning settings" (a reference-convention bar, user-decision style D11), last rule block.
  D two_phase_v9n_menu   from two_phase_v9m: LOCATED as a bound not a list, one primary per place among its elements, and a
                         sentence or block below decides for an element even where LOCATED does not name it.
  E two_phase_v9n_dbg    Phase 2 bar "Debug module registers" (a reference-convention bar), last bar before the keep blocks.
  python -B make_v9n.py [--write]
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
J, V9M = "two_phase_v9j", "two_phase_v9m"
OLD_CORE = ("4. Primary. Among the structural assets of step 3, label primary each element that 2.6 makes primary for this conceptual asset: "
            "where its value is stored or computed in this unit, where it crosses the unit's boundary whole, or, for a decision or setting, "
            "the element that holds or makes it. Outside a coprocessor, sequencing state (below) is not such a decision or setting.")
A_CORE = ("4. Primary. Among the structural assets of step 3, label primary each element that 2.6 makes primary for this conceptual asset, "
          "one element per place where the information is: where it crosses the unit's boundary whole, that port (or the signal handed whole "
          "to or from an instance, 2.6), never a register loaded from that port or driving it; where the unit stores or computes it without "
          "such a crossing, the one register or wire holding the value the other elements derive from; for a decision or setting, the one "
          "element that holds or makes it. A copy, a stage, a buffer, a partial or intermediate result, or a re-timed or derived flag of a "
          "value that already has its primary at that place is a path (2.7), not a second primary, unless a sentence or block below labels it "
          "primary. Outside a coprocessor, sequencing state (below) is not such a decision or setting.")
A2_SENT = (" A unit port, a hand-off, or an element a sentence or block below names is never the path of an internal element: where a port and a "
           "register hold the same value, the port is the primary and the register the path, and a done, wait, request, acknowledge, strobe or "
           "enable the unit drives or reads on a port keeps the label the port sentences and the blocks below give it.")
B_SENT = (" Mark each primary's confidence: \"sure\" when the RTL shows this element is the place 2.6 picks for this conceptual asset and no "
          "rule below could cover it; \"possible\" when another element could equally be that place, when the entry's lines leave the place in "
          "doubt, or when a rule's scope is unclear for it. A secondary's confidence is the empty string.")
B_OLD_KEY = '     "Label": "primary" | "secondary",\n'
B_NEW_KEY = '     "Label": "primary" | "secondary",\n     "Confidence": "sure" | "possible" | "",\n'
C_BLOCK = ("- Tuning settings.\n"
           "  Scope: a field of a peripheral's control or configuration register, written by a bus access, that apart from its read-back is read only "
           "by the unit's own engine, timer or interrupt logic to shape an output or an event the unit already has a concept for: a timing count or "
           "threshold, a phase or polarity choice, a strobe or framing length, an interrupt-select or interrupt-threshold bit, a data-direction, "
           "bit-order or format choice.\n"
           "  Criteria: (1) it is not an enable, a rate divider or prescaler, a lock, a mode choosing the protocol or the transfer kind, an address "
           "or device select, a key or a password; (2) no condition reads it to start, stop, abort or reset a transfer or to raise an error.\n"
           "  Exceptions: judged as usual: the settings criterion (1) names, and a setting the unit copies into engine state.\n"
           "  Outcome: it is part of the information of the output or event it shapes, not a piece of its own: keep no concept for it, name it in "
           "that concept's information, cite none of its lines as held lines (user decision 2026-10-18: reference convention).")
D_HEAD_OLD = "Step 4 reads it as written."
D_HEAD_NEW = ("Step 4 reads it as written: it bounds where a primary can be; it is not a list of primaries, and most of its elements are paths "
              "or nothing for this conceptual asset.")
D_PREC_OLD = ("when LOCATED names it. An element LOCATED does not name for this conceptual asset, wherever it stores, re-times, selects or computes "
              "the value and however the walk reached it, is a path to the primary (2.7: a copy kept while the value moves, a stage, a derived flag "
              "or result), not a primary, unless a sentence or block below labels it primary; it can be a secondary with its direction. LOCATED is "
              "fixed for this call: read it as written and add nothing to it, even where a held line seems to assign the element.")
D_PREC_NEW = ("when LOCATED names it. Among the elements LOCATED names for a conceptual asset, label primary one element per place where the "
              "information is (the port where it crosses the boundary whole, else the one register or wire holding the value the others derive "
              "from; for a decision or setting, the one element that holds or makes it); the others are paths (2.7). An element LOCATED does not "
              "name for this conceptual asset, wherever it stores, re-times, selects or computes the value and however the walk reached it, is a "
              "path to the primary (2.7: a copy kept while the value moves, a stage, a derived flag or result), not a primary, unless a sentence or "
              "block below labels it primary, which decides for that element even where LOCATED does not name it; it can be a secondary with its "
              "direction. LOCATED is fixed for this call: read it as written and add nothing to it on your own reading of the held lines; only a "
              "sentence or block below adds to it.")
E_BLOCK = ("- Debug module registers.\n"
           "  Scope: in a debug module or a debug transport unit (a unit whose ports are a debug bus, a test-access port or both, and whose "
           "registers are debug control, status, command, program-buffer or data-exchange registers), a signal or record field, never a port: "
           "such a register, a field of one, and the state of the machine serving those accesses.\n"
           "  Criteria: the debug bus, the test-access port or the hart's debug-mode accesses write it, and it is read to sequence, gate or "
           "report debug operations.\n"
           "  Exceptions: labelled as usual (2.6): the register selecting the hart, the register exchanging data with the hart, the "
           "authentication valid flag, a busy flag of the transport, and the unit's own ports (its halt and reset requests, its inputs): keep "
           "their concepts and their labels.\n"
           "  Outcome: it never qualifies as primary for any conceptual asset, although 2.6's storage and decision clauses and this step's "
           "decision-or-setting clause would make it primary; it can be a secondary (2.7) of the port or register the operation targets "
           "(user decision 2026-10-18: reference convention).")
FIRST_KEEP = "- Control record ports."

AD_P1 = "- Debug module registers.\n  Scope: a debug module or a debug transport unit (a unit whose ports are a debug bus, a test-access port or both, and whose registers are debug control, status, command, program-buffer or data-exchange registers). In it, a signal or record field, never a port: such a register or a field of one (an activation, halt, resume or reset control bit; a hart-halted, hart-reset or resume-acknowledge status; a command word, a command-error code, an automatic-execution setting, a program-buffer word; an authentication exchange word or state other than the valid flag), and the state of the machine serving those accesses.\n  Criteria: (1) the debug bus, the test-access port or the hart's debug-mode accesses write it, and it is read to sequence, gate or report debug operations; (2) it is not one of the spared elements below.\n  Exceptions:judged as usual (2.4, 4.4): the register selecting the hart, the register exchanging data with the hart, the authentication valid flag, a busy flag of the transport or module, and the unit's own ports (its halt and reset requests, its debug-bus and hart-side inputs and outputs).\n  Outcome: itonly holds or decides what the debug ports deliver: not a piece of its own, although step 2, step 3, Held outcomes, 2.4, 4.2 and 4.4 would keep it: keep no concept for it, name it in no concept's information, and cite no line assigning it as a held line. The spared elements and the unit's ports are judged as usual: keep their concepts and their labels (user decision 2026-10-19: reference convention)."
AD_P2 = "- Debug module registers.\n  Scope: a debug module or a debug transport unit (a unit whose ports are a debug bus, a test-access port or both, and whose registers are debug control, status, command, program-buffer or data-exchange registers). In it, a signal or record field, never a port: such a register or a field of one (an activation, halt, resume or reset control bit; a hart-halted, hart-reset or resume-acknowledge status; a command word, a command-error code, an automatic-execution setting, a program-buffer word; an authentication exchange word or state other than the valid flag), and the state of the machine serving those accesses.\n  Criteria: (1) the debug bus, the test-access port or the hart's debug-mode accesses write it, and it is read to sequence, gate or report debug operations; (2) it is not one of the spared elements below.\n  Exceptions:labelled as usual (2.6): the register selecting the hart, the register exchanging data with the hart, the authentication valid flag, a busy flag of the transport or module, and the unit's own ports (its halt and reset requests, its debug-bus and hart-side inputs and outputs): keep their concepts and their labels.\n  Outcome: itnever qualifies as primary for any conceptual asset, although 2.6's storage and decision clauses and examples, this step's decision-or-setting clause and its one-place sentence would make it primary; it can be a secondary (2.7) of the port or register the operation targets (user decision 2026-10-19: reference convention)."
P1_ANCHOR = "\n- Transfer records."


def rd(v, f):
    return (LAB / "prompts" / v / f).read_text(encoding="utf-8").replace("\r\n", "\n")


def build(name, src, files, readme, write):
    """files: {name: new text} for the changed files; the rest copied from src."""
    d = LAB / "prompts" / name
    crlf = b"\r\n" in (LAB / "prompts" / src / "phase2.md").read_bytes()
    if write:
        d.mkdir(exist_ok=True)
        for f in ("common.md", "phase1.md", "phase1_user.md", "phase2.md", "phase2_user.md"):
            if f in files:
                (d / f).write_bytes((files[f].replace("\n", "\r\n") if crlf else files[f]).encode("utf-8"))
            else:
                shutil.copyfile(LAB / "prompts" / src / f, d / f)
        (d / "README.md").write_text(f"# {name}: {readme} (built 2026-10-18; analysis/v10_diagnosis/make_v9n.py; PLAN_ISOLATE_CLUSTER_ORDER.md section 19)\n", encoding="utf-8")
        chk = bool(CK.check(name, log=lambda *a: None))
        nf = CH.new_format(name, 1) and CH.new_format(name, 2)
        s1, s2 = M.sha(CK.system(name, 1))[:12], M.sha(CK.system(name, 2))[:12]
        print(f"{name}: checker {chk}; new_format {nf}; sha12 {s1} / {s2}; changed {sorted(files)}")
        return chk and nf
    return True


def main(write):
    sys.stdout.reconfigure(encoding="utf-8")
    ok = True
    p2, p1 = rd(J, "phase2.md"), rd(J, "phase1.md")
    assert p2.count(OLD_CORE) == 1
    # A
    ok &= build("two_phase_v9n_place", J, {"phase2.md": p2.replace(OLD_CORE, A_CORE)}, "v9j with one primary per place in step 4's core sentence", write)
    # A2: A + a port-protection sentence (01:40, after A's three runs: the one-place sentence demoted ports and strobes)
    ok &= build("two_phase_v9n_place2", J, {"phase2.md": p2.replace(OLD_CORE, A_CORE + A2_SENT)}, "A plus: a unit port, a hand-off or an element a block below names is never the path of an internal element", write)
    # B
    assert p2.count(B_OLD_KEY) == 1
    b2 = p2.replace(OLD_CORE, OLD_CORE + B_SENT).replace(B_OLD_KEY, B_NEW_KEY)
    ok &= build("two_phase_v9n_conf", J, {"phase2.md": b2}, "v9j with a Confidence key on each asset row (sure / possible), scored sure-only and all", write)
    # C
    assert p1.count("\n\nOUTPUT") == 1
    before = p1[:p1.index("\n\nOUTPUT")].rstrip("\n").split("\n")[-1]
    assert before.startswith("  Outcome:"), before[:60]
    c1 = p1.replace("\n\nOUTPUT", "\n" + C_BLOCK + "\n\nOUTPUT", 1)
    ok &= build("two_phase_v9n_cfg", J, {"phase1.md": c1}, "v9j with the Phase 1 bar Tuning settings (reference convention) as the last rule block", write)
    # D
    m2, mu = rd(V9M, "phase2.md"), rd(V9M, "phase2_user.md")
    assert m2.count(D_HEAD_OLD) == 1 and m2.count(D_PREC_OLD) == 1
    ok &= build("two_phase_v9n_menu", V9M, {"phase2.md": m2.replace(D_HEAD_OLD, D_HEAD_NEW).replace(D_PREC_OLD, D_PREC_NEW)}, "v9m with LOCATED as a bound, one primary per place among its elements, and blocks below deciding even outside it", write)
    # E
    i4, i5 = p2.index("\n4. Primary."), p2.index("\n5. Secondary.")
    step4 = p2[i4:i5]
    assert step4.count("\n" + FIRST_KEEP) == 1
    k = step4.index("\n" + FIRST_KEEP)
    e2 = p2[:i4] + step4[:k].rstrip("\n") + "\n" + E_BLOCK + step4[k:] + p2[i5:]
    ok &= build("two_phase_v9n_dbg", J, {"phase2.md": e2}, "v9j with the Phase 2 bar Debug module registers (reference convention) as the last bar before the keep blocks", write)
    # AD: the paired debug-register bar on A (user 2026-10-19 morning, D95)
    a1, a2 = rd("two_phase_v9n_place", "phase1.md"), rd("two_phase_v9n_place", "phase2.md")
    assert a1.count(P1_ANCHOR) == 1
    before = a1[:a1.index(P1_ANCHOR)].rstrip("\n").split("\n")
    assert [l for l in before if l.startswith("- ")][-1].startswith("- Processor control-unit state."), "P1 insert point is not after the control-unit bar"
    n1 = a1.replace(P1_ANCHOR, "\n" + AD_P1 + P1_ANCHOR, 1)
    j4, j5 = a2.index("\n4. Primary."), a2.index("\n5. Secondary.")
    s4 = a2[j4:j5]
    assert s4.count("\n" + FIRST_KEEP) == 1
    kk = s4.index("\n" + FIRST_KEEP)
    n2 = a2[:j4] + s4[:kk].rstrip("\n") + "\n" + AD_P2 + s4[kk:] + a2[j5:]
    ok &= build("two_phase_v9n_place_dbg", "two_phase_v9n_place", {"phase1.md": n1, "phase2.md": n2}, "A (one primary per place) plus the paired Debug module registers bar: Phase 1 copy after the control-unit bar, Phase 2 copy as the last bar before the keep blocks (reference convention, D95)", write)
    print("ALL BUILT AND CHECKED" if ok else "CHECKS FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main("--write" in sys.argv)
