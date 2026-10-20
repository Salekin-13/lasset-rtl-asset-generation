"""Revision round of the v9k rules after their first Claude rule-alone read (read_v9k.json, v9k_packs.json; 2026-10-18).
Every edit is an asserted string replacement on rule_texts_v9k.json. Writes rule_texts_v9k2.json (the revised rules
only) and meta_v9k2.json. Sends nothing.

What each revision answers (from the packs):
  N21 P1   the port was often not listed at all (one repeat of cpu_regfile and cpu_lsu): the Outcome said the rule
           "keeps or drops no concept", so the agent did not count the port as kept. Now: each concept keeps the port
           as its entry or exit element.
  N22      the inter-core unit's read strobe only acknowledges the read (it drives an acknowledge field, returns no
           word): both repeats "unsure". Criterion (1) now names a read strobe that acknowledges or pops.
  N24 P2   wait_o (an inversion of a bus response field, which never qualifies) and cpu_irq_o (a one-bit reduction of
           the pending vector) were "unsure"; cpu_lsu rdata_o (a load's data) was read as a register read-back in one
           repeat. Criterion (1) adds the bus-record-field source and the reduction; the exception now says "a read of
           this unit's own registers".
  N25      shifter.cnt and bs_sign were "unsure" (criterion (2): the count is read only through run and done wires, the
           sign fill forms the result); wires (run, done) of other coprocessors were kept. Scope now covers registers and
           register fields, plus the sign-fill wire; criterion (2) reads through a wire computed from it alone, or the
           steps forming the result.
Cases moved from must-spare to expected harm (the rule cannot separate them from reference entries of the same shape;
reference convention): N24 cpu_lsu:mar_o, xbus:xbus_sel_o, xbus:xbus_tag_o; N25 cpu_cp_bitmanip:valid. Removed from the
intended cases: N21 cpu_control:ctrl_o (its module is not in the test plan); N24 debug_dm:ndmrstn_o (a reset output,
excluded by Scope on purpose: the watchdog's reset output of the same shape is not a reference entry).

  python -B make_v9k2_texts.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V9K = json.loads((HERE / "rule_texts_v9k.json").read_text(encoding="utf-8"))
META = json.loads((HERE / "meta_v9k.json").read_text(encoding="utf-8"))


def edit(text, old, new, rid, what):
    if text.count(old) != 1:
        raise SystemExit(f"{rid} {what}: the text to replace occurs {text.count(old)} times, not once:\n{old[:120]}")
    return text.replace(old, new)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = {}
    # N21 Phase 1
    t = dict(V9K["N21"])
    t["P1"] = edit(t["P1"], "the port, not the field, is the entry or exit. This rule keeps or drops no concept; the rules on the fields' "
                   "information still judge that information.",
                   "the port, not the field, is the entry or exit. Each such concept keeps the whole port as its entry or exit element "
                   "(it is that concept's \"Enters Through\" or \"Leaves Through\" port). This rule keeps or drops no concept of its own; "
                   "the rules on the fields' information still judge that information.", "N21", "P1 outcome")
    out["N21"] = t
    # N22, both wordings (the criteria text is shared)
    t = dict(V9K["N22"])
    for ph in ("P1", "P2"):
        t[ph] = edit(t[ph], "to let a register, FIFO or memory word take the written data, to return a stored word, or to pick which register the "
                     "access reaches;",
                     "to let a register, FIFO or memory word take the written data, to return a stored word or to acknowledge or pop the "
                     "read (a read strobe, even one that only drives an acknowledge), or to pick which register the access reaches;",
                     "N22", f"{ph} criteria")
    out["N22"] = t
    # N24 Phase 2
    t = dict(V9K["N24"])
    t["P2"] = edit(t["P2"], "Criteria: (1) the assignment driving the port reads that primary element or that conceptual asset's value, directly ",
                   "Criteria: (1) the assignment driving the port reads that primary element or that conceptual asset's value, or a field of "
                   "a bus request or response record port that no element of this unit holds before the port (2.6: the port is then the "
                   "element the access returns or decides), directly ", "N24", "P2 criterion 1 source")
    t["P2"] = edit(t["P2"], "(a gate, a select or a decode is no new value; an arithmetic or logic result from several operands is)",
                   "(a gate, a select, a decode, an inversion or a reduction of one element's bits to one bit is no new value; an "
                   "arithmetic or logic result from several operands is)", "N24", "P2 criterion 2")
    t["P2"] = edit(t["P2"], "Exceptions: not covered: the word returned for a register read (a read-data output or bus response answering an "
                   "access: 2.6 keeps a mixed read-back word a carrier);",
                   "Exceptions: not covered: the word returned for a read of this unit's own registers (a register read-back word, on a "
                   "read-data output or a bus response: 2.6 keeps a mixed read-back word a carrier; data a load returns from memory is "
                   "not such a word);", "N24", "P2 exception")
    out["N24"] = t
    # N25, both wordings (Scope and Criteria are shared)
    t = dict(V9K["N25"])
    for ph in ("P1", "P2"):
        t[ph] = edit(t[ph], "a register, register field or wire this unit's own statements assign (not a port, not an instance output): the busy "
                     "flag set when the operation starts and cleared when it ends or is aborted; the done flag telling that the last step is "
                     "reached, or its registered copy that releases the result; the step counter the operation loads at its start and counts "
                     "while busy; and an operand setting decoded from the instruction and an operand that the steps use (a sign fill, "
                     "signedness).",
                     "a register or register field this unit's own statements assign (not a port, not an instance output, not a wire, "
                     "except the operand setting named last): the busy flag set when the operation starts and cleared when it ends or is "
                     "aborted; the register holding the done flag that tells the last step is reached, or its registered copy that releases "
                     "the result; the step counter the operation loads at its start and counts while busy; and, the one wire covered, an "
                     "operand setting decoded from the instruction and an operand that every step uses (a sign fill, signedness).",
                     "N25", f"{ph} scope")
        t[ph] = edit(t[ph], "Criteria: (1) this unit assigns it in its own statements; (2) a condition reads it to advance, end or release the "
                     "operation, or the result or valid output is assigned from it.",
                     "Criteria: (1) this unit assigns it in its own statements; (2) a condition reads it, directly or through a wire computed "
                     "from it alone (a run or done wire), to advance, end or release the operation; or the result or valid output is assigned "
                     "from it; or the steps use it to form the result.", "N25", f"{ph} criteria")
    out["N25"] = t
    tmp = HERE / "_check_v9k2.json"
    tmp.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(HERE.parent / "check_new_rules.py"), str(tmp)], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-2500:])
    tmp.unlink()
    if r.returncode:
        sys.exit("checker BLOCKERS: nothing written")
    meta = {rid: dict(META[rid]) for rid in out}
    meta["N21"]["intended_cases"] = [c for c in META["N21"]["intended_cases"] if c != "neorv32_cpu_control:ctrl_o"]
    meta["N24"]["intended_cases"] = [c for c in META["N24"]["intended_cases"] if c != "neorv32_debug_dm:ndmrstn_o"]
    meta["N24"]["must_spare"] = ["neorv32_cpu_icc:csr_rdata_o"]
    meta["N24"]["expected_harm"] = ["neorv32_cpu_lsu:mar_o", "neorv32_xbus:xbus_sel_o", "neorv32_xbus:xbus_tag_o"]
    meta["N25"]["must_spare"] = ["neorv32_cpu_cp_shifter:shifter.sreg", "neorv32_cpu_cp_shifter:bs_result", "neorv32_cpu_cp_bitmanip:shifter.run",
                                 "neorv32_cpu_cp_bitmanip:clmul.run"]
    meta["N25"]["expected_harm"] = ["neorv32_cpu_cp_bitmanip:valid"]
    (HERE / "rule_texts_v9k2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "meta_v9k2.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    for rid, t in out.items():
        print(f"{rid:5} {t['title']:36} P1 {len((t['P1'] or '').split()):4}  P2 {len((t['P2'] or '').split()):4} words "
              f"(v9k: {len((V9K[rid]['P1'] or '').split())} / {len((V9K[rid]['P2'] or '').split())})")
    print("written rule_texts_v9k2.json, meta_v9k2.json")


if __name__ == "__main__":
    main()
