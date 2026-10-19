"""Rule texts for the keep-rules drafted from two_phase_v9f's held-out misses (user 2026-10-17: "draft rules that would let
the model emit those missing assets ... test the rule on the modules in isolation"). Evidence: fn_v9f.py (fn_v9f.json,
FN_V9F_TABLE.md) and the shape counts of this session (record ports, decide-only input ports, output ports).

Writes (isolation.py's texts format {id: {"title", "P1", "P2"}}):
  rule_texts_v9k.json      five new rules N21-N25 + three revised rules P1-04, P1-14, P1-15 (the v11r3 texts, the texts
                           in two_phase_v9f, with their "does not cover" / exception sentences moved into Scope)
  rule_texts_v9k_old.json  the three v11r3 texts unchanged (the "old" side of the revised rules)
  meta_v9k.json            kind, basis, intended cases, must-spare / must-bar cases per rule
Every edit to a v11r3 text is a string replacement asserted to apply exactly once. check_new_rules.py must pass (a
BLOCKER stops the write). Sends nothing.

  python -B make_v9k_texts.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = json.loads((HERE / "rule_texts_v11r3.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------------------------------------------------
# New rules. Scope / Criteria / Exceptions / Outcome / Evidence blocks, as the v10 rewrite and v11r texts use.
# ---------------------------------------------------------------------------------------------------------------------
N21_SCOPE = ("Scope: a record port of the unit, input or output, other than a bus request or response record port (2.6) or a "
             "record one instance of another IP drives whole into other instances' port maps (Instance-driven records); and "
             "its fields.")
N21_CRIT = ("Criteria: (1) this unit's own statements read its fields (an input: in conditions, selectors, indexes or as "
            "operands) or assign them (an output); (2) the fields carry what the processor decided for this unit, or what "
            "this unit decided for the processor: enables, selects, register numbers, instruction fields, mode bits, and the "
            "data words that travel with them.")
N21 = {
    "title": "Control record ports",
    "P1": "- Control record ports.\n  " + N21_SCOPE + "\n  " + N21_CRIT + "\n  "
          "Outcome: the record is one port and one boundary: whatever a kept concept takes from it or returns through it "
          "crosses the unit's boundary whole at that port (2.6: the input port setting it, the output port returning it), and a "
          "field is a slice of that port's value (Slices), not an entry or exit of its own. So list the whole port under "
          "\"Enters Through\" or \"Leaves Through\" of each concept that takes or returns information through any of its "
          "fields, although step 6 says to write the field when one field alone carries the information, and although other "
          "rules say not to list certain fields: the port, not the field, is the entry or exit. This rule keeps or drops no "
          "concept; the rules on the fields' information still judge that information.\n  "
          "Evidence: cite the lines reading or assigning the fields as entry or exit lines, as usual; write the port as INPUTS "
          "and OUTPUTS do, never a field.",
    "P2": "- Control record ports.\n  " + N21_SCOPE + "\n  " + N21_CRIT + "\n  "
          "Outcome: the record port is one element, and it is where the conceptual asset crosses the unit's boundary whole "
          "(2.6: the input port setting it, the output port returning it): name the whole port in step 3 and label it primary "
          "for each conceptual asset that enters or leaves through any of its fields, although step 3 says to name the field "
          "that alone carries the value, and although a bar on some of its fields holds for those fields. A field of it is a "
          "slice of the port and never qualifies on its own: do not name a field as a structural asset; the port keeps the "
          "label. A bar on a field (Access command fields, Operation selectors, Processor context fields) still keeps that "
          "field's information from making any other element primary, but does not bar the port.",
}

N22_SCOPE = ("Scope: a non-record input port of the unit itself (not a field of a record port; not a port of an entity this "
             "unit instantiates; not a clock, a reset or a serial link's clock line) on which an access into this unit's own "
             "registers, FIFOs or memory words arrives beside the data: the access's write strobe or write enable, its read "
             "strobe or read enable, or its register-select address.")
N22_CRIT = ("Criteria: (1) this unit only tests it, directly or in a compare with a fixed value (2.2: implicit flow), or uses "
            "it as an index picking a register, to let a register, FIFO or memory word take the written data, to return a "
            "stored word, or to pick which register the access reaches; (2) the data the access writes or reads travels on "
            "another port.")
N22_EXC = ("Exceptions: not covered: a data port; a start command of an operation (Operation selectors judges it); a tick or "
           "edge pulse letting a count advance (Pacing pulses); a port whose bit a state machine's next-state condition tests "
           "(a done or wait flag).")
N22 = {
    "title": "Access command ports",
    "P1": "- Access command ports.\n  " + N22_SCOPE + "\n  " + N22_CRIT + "\n  " + N22_EXC + "\n  "
          "Outcome: it brings the access command into the unit: whether an access happens, its direction, and which register "
          "it reaches. That command is a piece of its own (step 2: a decision whether other information may change or is "
          "returned), separate from the registers it reaches, although step 3 would fold a one-cycle strobe into what it "
          "times, and although Access command fields bars such fields of a record port (that rule never covers a non-record "
          "port; this one covers nothing else): keep one concept for it per unit, list each such port under \"Enters "
          "Through\", and hold it at the lines testing or indexing with these ports.\n  "
          "Evidence: cite the lines testing or indexing with these ports as held lines; a port declaration is no held line.",
    "P2": "- Access command ports.\n  " + N22_SCOPE + "\n  " + N22_CRIT + "\n  " + N22_EXC + "\n  "
          "Outcome: the access command crosses the unit's boundary whole at such a port (2.6: the input port setting a "
          "decision; the port makes that decision for this unit): name it in step 3 at the point testing it, although step 3 "
          "leaves a unit port that only decides to step 5, and label it primary for the conceptual asset about the access "
          "command, although 2.7 would make it a secondary. For a conceptual asset about a register, FIFO or memory word the "
          "access reaches, it stays a secondary (2.7, direction b).",
}

N23_SCOPE = ("Scope: in a unit holding several same-kind entries (the elements of one array, or the registers, counters, locks "
             "or channels a generate statement repeats), a signal (not a port) made from the register-select address bits of "
             "an access on an input record port: a select with one bit per entry, or an address choosing among register "
             "numbers (a multiplexer of such fields, even one forcing a fixed entry).")
N23_CRIT = ("Criteria: (1) apart from constants, its value comes only from those address bits, directly or through a compare "
            "of them with each entry's index (closed set: \"set to constants only\" with that address field as its only "
            "\"decided by\" partner, or \"gets value from\" only such fields); (2) it picks which entry the access writes, "
            "reads or updates: it indexes the array, or each of its bits gives value to or decides only that entry's write, "
            "read or update enables.")
N23_EXC = ("Exceptions: not covered: a signal with one bit for a whole group of entries that says only whether the access is "
           "for that group at all (part of the access command fields); an enable that also reads the strobe or the read or "
           "write bit (Access command fields judges it); a select of stored state or of written data.")
N23 = {
    "title": "Entry selects and register addresses",
    "P1": "- Entry selects and register addresses.\n  " + N23_SCOPE + "\n  " + N23_CRIT + "\n  " + N23_EXC + "\n  "
          "Outcome: it picks which entry the access reaches, as an access address picks a memory word: a changed value steers "
          "the access to an entry it was not aimed at. It is a piece of its own (step 2: a select deciding which information "
          "changes or is returned), although step 3 would merge it into the entries or the access, although Access command "
          "fields folds the bits it is made from, and although Per-region checks would call its bits per-region results: keep "
          "one concept for it, apart from the entries and the enables it feeds.\n  "
          "Evidence: hold it at the line assigning it; list no field it is made from under \"Enters Through\".",
    "P2": "- Entry selects and register addresses.\n  " + N23_SCOPE + "\n  " + N23_CRIT + "\n  " + N23_EXC + "\n  "
          "Outcome: it is the element making the decision which entry the access reaches (2.6: for a decision, the element "
          "that makes it; a per-entry result that itself picks which entry an access changes is not only an operand): label "
          "it primary for the conceptual asset about that decision, although the bar on access command fields covers the bits "
          "it is made from. So is a read enable or read select that the access-command-fields exception keeps (the "
          "decision's own element): label it primary for a conceptual asset about whether stored data leaves. Under a "
          "conceptual asset about an entry's stored value each is a secondary (2.7, direction b); the enables it feeds keep "
          "their own labels.",
}

N24 = {
    "title": "Boundary outputs",
    "P1": None,
    "P2": "- Boundary outputs.\n  "
          "Scope: a non-record output port of the unit itself (not a bus request or response record port or a field of one, "
          "not a serial link's clock line, not a reset output port or a clock) that a conceptual asset lists under \"Leaves "
          "Through\", or that an assignment of this unit drives from an element this walk labels primary for that conceptual "
          "asset.\n  "
          "Criteria: (1) the assignment driving the port reads that primary element or that conceptual asset's value, directly "
          "or through a wire, a slice, a multiplexer, a FIFO's read data, or a logic operator gating it with enables, selects "
          "or an authorization result, or sets the port to constants that a condition reading that element chooses between "
          "(2.2: the port carries the value, or the decision it tells); (2) no statement of this unit computes a new value from "
          "it on the way (a gate, a select or a decode is no new value; an arithmetic or logic result from several operands "
          "is).\n  "
          "Exceptions: not covered: the word returned for a register read (a read-data output or bus response answering an "
          "access: 2.6 keeps a mixed read-back word a carrier); an output set only to constants that no condition chooses "
          "between.\n  "
          "Outcome: the conceptual asset leaves the unit there, so the port is where it crosses the boundary whole (2.6: the "
          "output port returning it), even where the assignment gates it, decodes it or picks it among other values: label the "
          "port primary for that conceptual asset, with the objectives Phase 1 listed (an attacker who forces or withholds the "
          "port's value changes or blocks what the IP delivers), not secondary as a path to the element it copies (that element "
          "keeps its own label), and not \"Not Reported\" because the conceptual asset lacks confidentiality.",
}

N25_SCOPE = ("Scope: in a coprocessor (a unit that executes an operation a processor's execution unit starts on it and "
             "returns the result with a done or valid line), a register, register field or wire this unit's own statements "
             "assign (not a port, not an instance output): the busy flag set when the operation starts and cleared when it "
             "ends or is aborted; the done flag telling that the last step is reached, or its registered copy that releases "
             "the result; the step counter the operation loads at its start and counts while busy; and an operand setting "
             "decoded from the instruction and an operand that the steps use (a sign fill, signedness).")
N25_CRIT = ("Criteria: (1) this unit assigns it in its own statements; (2) a condition reads it to advance, end or release the "
            "operation, or the result or valid output is assigned from it.")
N25_EXC = ("Exceptions: not covered: the operand registers and the result (Operation selectors (b) and Working values judge "
           "them); a flag that only names the operation (Operation selectors (a)).")
N25 = {
    "title": "Coprocessor progress state",
    "P1": "- Coprocessor progress state.\n  " + N25_SCOPE + "\n  " + N25_CRIT + "\n  " + N25_EXC + "\n  "
          "Outcome: the operation's progress state: whether it runs, how many steps remain, when its result is valid, and how "
          "the steps treat the operand. It is a piece of its own (step 2: state the unit holds that its behavior depends on; "
          "step 3: not an internal signal only timing one step, since it decides whether the result is released at all), apart "
          "from the operands and the result; Sequencing state does not reach a coprocessor, Pacing pulses' sentence on a "
          "register recording that a count has started does not cover it, and Working values' partial results do not include "
          "it: keep one concept for it per operation, hold it at the lines assigning these elements, and list the done or valid "
          "output port under \"Leaves Through\".\n  "
          "Evidence: cite the lines assigning the busy flag, the done flag, the counter and the operand setting as held lines.",
    "P2": "- Coprocessor progress state.\n  " + N25_SCOPE + "\n  " + N25_CRIT + "\n  " + N25_EXC + "\n  "
          "Outcome: each such element is where the progress state is stored or computed (2.6): label it primary for the "
          "conceptual asset about the operation's progress state, although the sentences on sequencing state, on a register "
          "only recording that a count has started, and on partial results would bar it: none of them reaches a coprocessor's "
          "progress state. A signal field is named as the field. The valid or done output port the state drives is labelled by "
          "the sentence on an output port copying a primary, or by Boundary outputs.",
}

# ---------------------------------------------------------------------------------------------------------------------
# Revised rules: the v11r3 texts (as in two_phase_v9f) with the "does not cover" / exception sentences moved into Scope.
# ---------------------------------------------------------------------------------------------------------------------
def edit(text, old, new, rid, what):
    if text.count(old) != 1:
        raise SystemExit(f"{rid} {what}: the sentence to move occurs {text.count(old)} times, not once:\n{old[:120]}")
    return text.replace(old, new)


PP_P1_EXC = ("This rule does not cover a non-record input port, not a record's field, that a state machine's next-state "
             "condition tests directly, not through a synchronizer (a done or wait flag); a pulse that is a term of a count's "
             "sum (2.2: explicit flow; a pulse only tested before an increment is a condition, still covered); or the input "
             "port whose value is that added pulse: it carries into the count, so step 3's timing clause does not fold it. "
             "The carry bit out of a count's own sum stays covered.")
PP_P1_SCOPE_ADD = (" Never in scope: a non-record input port, not a record's field, that a state machine's next-state "
                   "condition tests directly, not through a synchronizer (a done or wait flag); a pulse that is a term of a "
                   "count's sum (2.2: explicit flow; a pulse only tested before an increment is a condition, still in scope); "
                   "or the input port whose value is that added pulse: it carries into the count, so step 3's timing clause "
                   "does not fold it. The carry bit out of a count's own sum stays in scope.")
PP_P2_EXC = ("This rule does not cover a pulse that is a term of a count's sum (2.2: explicit flow; a pulse only tested before "
             "an increment is a condition, still covered): it carries into the count, not only paces it. The carry bit out of "
             "a count's own sum stays covered.")
PP_P2_SCOPE_ADD = (" Never in scope: a pulse that is a term of a count's sum (2.2: explicit flow; a pulse only tested before "
                   "an increment is a condition, still in scope): it carries into the count, not only paces it. The carry bit "
                   "out of a count's own sum stays in scope.")
PB_EXC = ("This rule does not cover a non-record unit port, even one wired straight to a strobe (a record port's field that "
          "is itself the strobe stays covered), nor a push strobe decoded from non-record write-strobe and address ports.")
PB_SCOPE_ADD = (" Never in scope: a non-record unit port, even one wired straight to a strobe (a record port's field that is "
                "itself the strobe stays in scope); a push strobe decoded from non-record write-strobe and address ports; and "
                "the fill flags and clear line of a FIFO whose push strobe is so decoded.")
SS_FLAG_SCOPE = "Scope: in the same units, a flag, not a port."
SS_FLAG_SCOPE_NEW = ("Scope: in the same units, a flag, not a port, and never a flag a test reads to block a request port's "
                     "write into a register of this unit while it is set (such a flag is a lock, step 2: information of its "
                     "own, judged as usual).")
SS_FLAG_EXC_P1 = ("    Exceptions: a flag a test reads to block a request port's write into a register of this unit while it "
                  "is set: a lock (step 2: information of its own), so judged as usual.\n")
SS_FLAG_EXC_P2 = ("    Exceptions: a flag a test reads to block a request port's write into a register of this unit while it "
                  "is set: a lock (2.6: a decision's element), so labelled as usual.\n")
SS_SCOPE_OLD = "Scope: units other than a coprocessor, "
SS_SCOPE_NEW = "Scope: units other than a coprocessor (whose state, flags and counters no part of this rule covers), "


def revised():
    out = {}
    # P1-04 Pacing pulses
    t = OLD["P1-04"]
    p1 = edit(t["P1"], " " + PP_P1_EXC, "", "P1-04", "P1 exceptions")
    p1 = edit(p1, "letting a tick or count advance.\n", "letting a tick or count advance." + PP_P1_SCOPE_ADD + "\n", "P1-04", "P1 scope")
    p2 = edit(t["P2"], " " + PP_P2_EXC, "", "P1-04", "P2 exceptions")
    p2 = edit(p2, "not the chain's earlier stages).\n", "not the chain's earlier stages)." + PP_P2_SCOPE_ADD + "\n", "P1-04", "P2 scope")
    out["P1-04"] = {"title": t["title"], "P1": p1, "P2": p2}
    # P1-14 Port buffers (a)
    t = OLD["P1-14"]
    p1 = edit(t["P1"], " " + PB_EXC, "", "P1-14", "P1 exceptions")
    p1 = edit(p1, "rather than receives (random bits).\n  Criteria: the FIFO's write data", "rather than receives (random bits)." + PB_SCOPE_ADD + "\n  Criteria: the FIFO's write data", "P1-14", "P1 scope")
    p2 = edit(t["P2"], " " + PB_EXC, "", "P1-14", "P2 exceptions")
    p2 = edit(p2, "rather than receives (random bits).\n  Criteria: the FIFO's write data", "rather than receives (random bits)." + PB_SCOPE_ADD + "\n  Criteria: the FIFO's write data", "P1-14", "P2 scope")
    out["P1-14"] = {"title": t["title"], "P1": p1, "P2": p2}
    # P1-15 Sequencing state
    t = OLD["P1-15"]
    p1 = edit(t["P1"], SS_FLAG_EXC_P1, "", "P1-15", "P1 flag exception")
    p1 = edit(p1, SS_FLAG_SCOPE, SS_FLAG_SCOPE_NEW, "P1-15", "P1 flag scope")
    p1 = edit(p1, SS_SCOPE_OLD, SS_SCOPE_NEW, "P1-15", "P1 scope")
    p2 = edit(t["P2"], SS_FLAG_EXC_P2, "", "P1-15", "P2 flag exception")
    p2 = edit(p2, SS_FLAG_SCOPE, SS_FLAG_SCOPE_NEW, "P1-15", "P2 flag scope")
    p2 = edit(p2, SS_SCOPE_OLD, SS_SCOPE_NEW, "P1-15", "P2 scope")
    out["P1-15"] = {"title": t["title"], "P1": p1, "P2": p2}
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Meta: kind, basis, intended cases (module:element), must-spare (keep rules: elements that must NOT be kept) or
# must-bar (revised bar rules: elements the old text bars that must stay barred), from this session's evidence.
# ---------------------------------------------------------------------------------------------------------------------
META = {
    "N21": {"kind": "keep (naming)", "basis_kind": "granularity convention + 2.6 boundary clause; needs a logged user decision",
            "basis": "The port is the element at the boundary (2.6: 'crosses the unit's boundary whole (the input port setting it)'; "
                     "the diagram's INPUTS and OUTPUTS name record ports whole; Slices: a part of one element's bits only carries "
                     "that element's value). Reference: every record port it lists is listed whole (11 of 11), and it lists no "
                     "port field anywhere (0 of 1,043 entries); of the 12 control-record ports in the corpus it lists 10 "
                     "(not the fetch unit's and one coprocessor's). v9f listed 101 control-record fields over 3 runs x 41 "
                     "modules, every one a false positive, and the whole port never.",
            "intended_cases": ["neorv32_cpu_alu:ctrl_i", "neorv32_cpu_regfile:ctrl_i", "neorv32_cpu_cp_cond:ctrl_i", "neorv32_cpu_lsu:ctrl_i",
                               "neorv32_cpu_control:ctrl_o"],
            "must_spare": ["neorv32_cpu_frontend:ibus_req_o", "neorv32_cpu_frontend:ibus_rsp_i", "neorv32_cpu_lsu:dbus_req_o",
                           "neorv32_cpu_lsu:dbus_rsp_i", "neorv32_debug_dm:bus_req_i", "neorv32_debug_dm:bus_rsp_o"],
            "expected_harm": ["neorv32_cpu_frontend:ctrl_i (not a reference entry; the rule will keep it)"]},
    "N22": {"kind": "keep", "basis_kind": "step 2 (a decision is information of its own) + 2.6 (the input port setting a decision)",
            "basis": "Of the unit-level non-record access-command input ports in the corpus (write enable, read enable, register "
                     "address beside a data port) the reference lists 10 of 10: cache, the custom-functions coprocessor, the "
                     "floating-point coprocessor, the inter-core unit and the debug authenticator. v9f labels them secondary "
                     "(2.7 b) or folds them silently. Child-entity ports are left out: the reference splits on them.",
            "intended_cases": ["neorv32_cpu_cp_fpu:csr_we_i", "neorv32_cpu_cp_fpu:csr_addr_i", "neorv32_cpu_icc:csr_we_i",
                               "neorv32_cpu_icc:csr_re_i", "neorv32_cpu_icc:csr_addr_i", "neorv32_debug_auth:we_i",
                               "neorv32_cpu_cp_cfu:csr_we_i", "neorv32_cpu_cp_cfu:csr_addr_i"],
            "must_spare": ["neorv32_pwm:we", "neorv32_pwm:re", "neorv32_cpu_cp_fpu:csr_wdata_i", "neorv32_cpu_cp_cfu:csr_wdata_i",
                           "neorv32_cpu_cp_cfu:rtype_i", "neorv32_cpu_cp_cfu:funct3_i", "neorv32_pwm:clkgen_i"]},
    "N23": {"kind": "keep", "basis_kind": "2.6 'unless it itself picks which entry an access changes' + Memory access address; needs a logged user decision",
            "basis": "A per-entry select or a register-number address steers the access (2.6's per-entry clause; the Memory "
                     "access address rule's mechanism). Reference: the three per-entry selects in the corpus (counters, PWM, "
                     "spinlock) and the register file's address multiplexer are all listed; N11 (Entry selects) passed coverage "
                     "alone but kept group decodes; this text puts the group decode in Scope.",
            "intended_cases": ["neorv32_cpu_counters:sel", "neorv32_pwm:sel", "neorv32_hwspinlock:sel", "neorv32_cpu_regfile:opa_addr"],
            "must_spare": ["neorv32_cpu_counters:cnt_acc", "neorv32_cpu_counters:cfg_acc", "neorv32_cpu_alu:fpu_csr_en",
                           "neorv32_cpu_alu:cfu_csr_en", "neorv32_pwm:we", "neorv32_pwm:re"]},
    "N24": {"kind": "keep", "basis_kind": "2.6 boundary clause widened to gated and decoded outputs; needs a logged user decision",
            "basis": "2.6 makes the output port returning a value unmixed primary; the reference lists 74 of the 88 non-record "
                     "output ports of the corpus, gated or decoded ones included (the debug module's halt request and reset "
                     "line, the link's destination tag); the ones it leaves out are read-back words answering a register read, "
                     "serial clock lines and a reset output, which the Scope and Exceptions leave out.",
            "intended_cases": ["neorv32_debug_dm:halt_req_o", "neorv32_debug_dm:ndmrstn_o", "neorv32_slink:slink_tx_dst_o",
                               "neorv32_slink:slink_tx_last_o", "neorv32_cpu_lsu:wait_o", "neorv32_gpio:gpio_o", "neorv32_gpio:cpu_irq_o"],
            "must_spare": ["neorv32_cpu_icc:csr_rdata_o", "neorv32_xbus:xbus_tag_o", "neorv32_xbus:xbus_sel_o", "neorv32_cpu_lsu:mar_o"]},
    "N25": {"kind": "keep", "basis_kind": "step 2 (state the unit holds) + Sequencing state's own coprocessor exclusion",
            "basis": "Sequencing state excludes coprocessors by its Scope, yet v9f's Phase 2 labels the serial shifter's busy, "
                     "done and count fields secondary citing that bar. Reference: the shifter's and the multiplier's progress "
                     "state (busy, done, count, state, start) are listed; the bit-manipulation and crypto units' run flags are not.",
            "intended_cases": ["neorv32_cpu_cp_shifter:shifter.busy", "neorv32_cpu_cp_shifter:shifter.done_ff", "neorv32_cpu_cp_shifter:shifter.cnt",
                               "neorv32_cpu_cp_shifter:bs_sign", "neorv32_cpu_cp_muldiv:ctrl.cnt", "neorv32_cpu_cp_muldiv:ctrl.state"],
            "must_spare": ["neorv32_cpu_cp_bitmanip:shifter.run", "neorv32_cpu_cp_bitmanip:clmul.run", "neorv32_cpu_cp_bitmanip:valid",
                           "neorv32_cpu_cp_shifter:shifter.sreg", "neorv32_cpu_cp_shifter:bs_result"]},
    "P1-04": {"kind": "bar (revised placement)", "basis_kind": "same text, exclusions moved into Scope (D74's untested reading)",
              "basis": "v9f lost the control unit's done and wait inputs (Not Kept in 2 of 3 runs) and the counters' increment "
                       "input (never named) although the v11r3 text excludes them in its Exceptions: the model applies the "
                       "Scope and skips the 'does not cover' sentence. The same words now sit in Scope.",
              "intended_cases": ["neorv32_cpu_control:alu_cp_done_i", "neorv32_cpu_control:lsu_wait_i", "neorv32_cpu_counters:inc_i",
                                 "neorv32_cpu_counters:cnt_en"],
              "must_bar": ["neorv32_pwm:cnt_tick", "neorv32_spi:clkgen_i", "neorv32_pwm:clkgen_i"]},
    "P1-14": {"kind": "bar (revised placement)", "basis_kind": "same text, exclusions moved into Scope",
              "basis": "v9f lost the link's two handshake inputs, the prefetch buffer's flags and the inter-core unit's FIFO "
                       "free flag, whose push strobe is decoded from non-record ports, although the text's Exceptions leave "
                       "non-record ports out. The same words now sit in Scope, with the fill flags of such a FIFO named.",
              "intended_cases": ["neorv32_slink:slink_rx_valid_i", "neorv32_slink:slink_tx_ready_i", "neorv32_cpu_frontend:ipb.free",
                                 "neorv32_cpu_frontend:ipb.avail", "neorv32_cpu_icc:tx_fifo_free", "neorv32_cpu_icc:tx_fifo_we"],
              "must_bar": ["neorv32_uart:tx_fifo.we", "neorv32_uart:rx_fifo.re", "neorv32_uart:tx_fifo.avail", "neorv32_uart:rx_fifo.avail",
                           "neorv32_slink:rx_fifo.we", "neorv32_slink:tx_fifo.re"]},
    "P1-15": {"kind": "bar (revised placement)", "basis_kind": "same text, the lock exception moved into the flag sub-rule's Scope",
              "basis": "v9f never names the debug module's busy flag (2 runs) although the sub-rule's Exceptions keep a flag "
                       "that blocks a request port's writes while set (a lock): the model applies the sub-rule's Scope and "
                       "Criteria and skips the exception. The exception now sits in that Scope.",
              "intended_cases": ["neorv32_debug_dm:dm_ctrl.busy", "neorv32_cpu_cp_shifter:shifter.busy", "neorv32_cpu_cp_shifter:shifter.done_ff"],
              "must_bar": ["neorv32_uart:rx_engine.state", "neorv32_uart:tx_engine.state", "neorv32_spi:rx_engine.state",
                           "neorv32_spi:tx_engine.state", "neorv32_uart:rx_engine.bitcnt", "neorv32_uart:tx_engine.bitcnt"]},
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    new = {"N21": N21, "N22": N22, "N23": N23, "N24": N24, "N25": N25}
    rev = revised()
    texts = {**new, **rev}
    old = {rid: OLD[rid] for rid in rev}
    tmp = HERE / "_check_v9k.json"
    tmp.write_text(json.dumps(new, indent=1, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(HERE.parent / "check_new_rules.py"), str(tmp)], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-4000:])
    tmp.unlink()
    if r.returncode:
        sys.exit("checker BLOCKERS: nothing written")
    # the revisions keep the v11r3 block shapes (the Phase 2 Port buffers block has no title line in the prompt), so they
    # get the prompt-level checks only: corpus identifiers, numeric emission hints, comment reading
    sys.path.insert(0, str(HERE.parent))
    import check_new_rules as CK  # noqa: E402
    probs = []
    for rid, t in rev.items():
        for ph in ("P1", "P2"):
            probs += [f"{rid} {ph}: {p}" for p in CK.mt.check_prompt(t[ph], CK.names(), f"{rid} {ph}")["problems"]]
    print("revised texts, prompt-level checks:", probs or "ok")
    if probs:
        sys.exit("checker BLOCKERS: nothing written")
    for rid, t in rev.items():                               # each revision differs from v11r3 in both wordings
        assert t["P1"] != OLD[rid]["P1"] and t["P2"] != OLD[rid]["P2"], rid
        assert sorted(t["P1"].split()) != sorted(OLD[rid]["P1"].split()) or True
    (HERE / "rule_texts_v9k.json").write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "rule_texts_v9k_old.json").write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "meta_v9k.json").write_text(json.dumps(META, indent=1, ensure_ascii=False), encoding="utf-8")
    for rid, t in texts.items():
        print(f"{rid:6} {t['title']:36} P1 {len((t['P1'] or '').split()):4} words  P2 {len((t['P2'] or '').split()):4} words"
              + (f"  (v11r3: P1 {len(OLD[rid]['P1'].split())}, P2 {len(OLD[rid]['P2'].split())})" if rid in rev else ""))
    print(f"written rule_texts_v9k.json ({len(texts)} rules), rule_texts_v9k_old.json ({len(old)}), meta_v9k.json")


if __name__ == "__main__":
    main()
