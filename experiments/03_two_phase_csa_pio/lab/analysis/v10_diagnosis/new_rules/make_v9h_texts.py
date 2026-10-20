"""Stage C, first cell (PLAN_ISOLATE_CLUSTER_ORDER.md section 8; user 2026-10-18: "Build the four keep blocks for the
FIFO-flag and handshake cluster ... run the checker, and give me the cell's cost before sending anything"): four keep
blocks written as the five v9k rules were (Scope / Criteria / Exceptions / Outcome / Evidence, a positive outcome, both
phases), each for an exclusion of a K1 bar that guards reference entries v9g still misses:
  K11 Done and wait inputs      Pacing pulses' exclusion (the control unit's done and wait inputs; v9g: named in run 0 only)
  K12 Link handshake ports      Port buffers' non-record-port exclusion (the link's valid and ready inputs; never named)
  K13 Busy locks                Sequencing state's lock exception (the debug module's busy flag; never named)
  K14 Count increment inputs    Pacing pulses' "term of the sum" exclusion (the counters' increment input; never named)
Shapes across the 41 modules (k1_shapes workflow, 2026-10-18) set the Scope and the meta's must-spare lists.
Writes rule_texts_v9h.json and meta_v9h.json; check_new_rules.py must pass. Sends nothing.

  python -B make_v9h_texts.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

K11_SCOPE = ("Scope: a one-bit non-record input port of the unit itself (not a record field, not a port of an entity this unit "
             "instantiates, not a clock, a reset or a serial link's clock line) that a condition of this unit tests to pick a state "
             "machine's next state, or to clear the one-bit flag that holds an access pending.")
K11_CRIT = ("Criteria: (1) the test lets the unit leave a state, or clear a pending flag, in which it waits for an operation "
            "another unit or device performs (the condition's other branch keeps the state or the flag, and the unit moves on "
            "only once the port shows the operation done, valid, ready, acknowledged, failed or no longer busy); (2) the port comes "
            "from the unit or device performing that operation (judge from the port names at either end, and say so).")
K11_EXC = ("Exceptions: not covered: a command or enable that starts, clears or gates something (step 2 judges it as usual); "
           "a request held until served; a tick letting a count advance (Pacing pulses); a port whose bit synchronizer stages "
           "re-sample first (Sequencing state's port sub-rule judges it).")
K11 = {"title": "Done and wait inputs",
       "P1": "- Done and wait inputs.\n  " + K11_SCOPE + "\n  " + K11_CRIT + "\n  " + K11_EXC + "\n  "
             "Outcome: it brings the peer's status into this unit: whether the operation this unit waits for has ended. That status "
             "is a piece of its own (step 1: a response signalled by another module; step 2: a decision whether this unit advances), "
             "although step 3 would fold a one-cycle flag into what it times and although Pacing pulses names an input port letting "
             "a count advance: keep one concept for it, list the port under \"Enters Through\", and hold it at the lines testing it.\n  "
             "Evidence: cite the lines testing the port as held lines; name the state machine and the operation waited for.",
       "P2": "- Done and wait inputs.\n  " + K11_SCOPE + "\n  " + K11_CRIT + "\n  " + K11_EXC + "\n  "
             "Outcome: the status crosses the unit's boundary whole at that port (2.6: the input port setting a decision): name it in "
             "step 3 at the point testing it, although step 3 leaves a port that only decides to step 5, and label it primary for "
             "the conceptual asset about that status, although 2.7 would make it a secondary. For a conceptual asset about the "
             "state machine's step or about the data the operation returns, it stays a secondary (2.7, direction b)."}

K12_SCOPE = ("Scope: a non-record port of the unit itself on a streaming or serial link to a peer device or module, other than "
             "the link's data lines, its clock line and any bus request or response record: an input port wired straight, or "
             "through one register, into a FIFO instance's push or pop strobe input; an output port driven from a FIFO's fill "
             "flag, or from a register telling the peer whether this unit can accept or has a word; and a flow-control or "
             "chip-select line, even one that reaches the unit's strobes only through synchronizer stages and its state machine "
             "(judge from the port names which lines are the link's handshake, and say so).")
K12_CRIT = ("Criteria: (1) the port's value decides, at this unit's boundary, whether a word moves across the link; (2) the "
            "word it qualifies travels on other ports of the same link.")
K12_EXC = ("Exceptions: not covered: the unit's internal strobes, fill flags and clear lines of the FIFO (Port buffers judges "
           "them); the link's data ports (Forwarded transactions and Port buffers judge them); the link's clock line (Clocks "
           "and resets).")
K12 = {"title": "Link handshake ports",
       "P1": "- Link handshake ports.\n  " + K12_SCOPE + "\n  " + K12_CRIT + "\n  " + K12_EXC + "\n  "
             "Outcome: the handshake is the link's transfer protocol at this unit's boundary: whether the peer offers or accepts "
             "a word, and whether this unit does. It is a piece of its own (step 1: a request or response signalled to or from "
             "another module; a line held still blocks every transfer), although step 3 would fold it into the word it times and "
             "although Port buffers bars the strobes and flags it is wired to: keep one concept per link direction for the "
             "handshake, list each such port under \"Enters Through\" or \"Leaves Through\", and hold it at the lines wiring or "
             "assigning the port.\n  "
             "Evidence: cite the lines wiring the port to the FIFO's strobe, or driving it from the flag, as held lines; cite no "
             "line assigning the internal strobe or flag as a held line.",
       "P2": "- Link handshake ports.\n  " + K12_SCOPE + "\n  " + K12_CRIT + "\n  " + K12_EXC + "\n  "
             "Outcome: the handshake crosses the unit's boundary whole at the port (2.6: the input port setting the decision, the "
             "output port returning it): name each such port in step 3 and label it primary for the handshake's conceptual asset, "
             "although step 3 leaves a port that only decides to step 5, although the Port buffers sentences bar the internal "
             "strobe or flag the port is wired to (that bar covers the internal element, never the port), and although 2.7 would "
             "make the port a secondary. The internal strobe or flag stays barred; the port is the primary."}

K13_SCOPE = ("Scope: in a unit other than a coprocessor, a flag of this unit, not a port: a register, or a wire decoded from the "
             "state register alone.")
K13_CRIT = ("Criteria: (1) its value tells whether a multi-step operation of this unit is in progress (set at the start or "
            "decoded from the state, cleared at the end); (2) a condition reads it to refuse or delay a write from a request port "
            "(a bus or debug-interface record port) into a register of this unit, or to refuse a new command, while it is set.")
K13_EXC = ("Exceptions: not covered: a busy flag read only for a status read-back, for an output port or for the engine's own "
           "steps (Sequencing state's busy sub-rule judges it); a flag of a coprocessor (Coprocessor progress state).")
K13 = {"title": "Busy locks",
       "P1": "- Busy locks.\n  " + K13_SCOPE + "\n  " + K13_CRIT + "\n  " + K13_EXC + "\n  "
             "Outcome: a lock (step 2: a lock deciding whether other information may change): it refuses writes while the operation "
             "runs. It is a piece of its own, apart from the state it is decoded from, although Sequencing state's busy sub-rule "
             "would fold a busy flag decoded from sequencing state into that state: keep one concept for it, and hold it at the line "
             "assigning it.\n  "
             "Evidence: cite the line assigning the flag as its held line, and the lines where it blocks a write as the mechanism.",
       "P2": "- Busy locks.\n  " + K13_SCOPE + "\n  " + K13_CRIT + "\n  " + K13_EXC + "\n  "
             "Outcome: the flag is the element making the lock decision (2.6: for a decision, the element that makes it): label it "
             "primary for the conceptual asset about the lock, although the sequencing-state sentences would bar a busy flag decoded "
             "from sequencing state (they do not reach a flag that blocks writes); for the registers it protects it is a secondary "
             "(2.7, direction b)."}

K14_SCOPE = ("Scope: a non-record input port of the unit, or of an entity of this file that the unit instantiates, that carries "
             "the pulse a count adds: the port, or a wire that only copies or widens it, is a term of the sum forming the count's "
             "next value (2.2: explicit flow).")
K14_CRIT = ("Criteria: (1) the port is a term of that sum, not only a condition letting the count advance; (2) the count is "
            "information the unit holds (a counter software reads, or whose value decides an event).")
K14_EXC = ("Exceptions: not covered: a tick or edge pulse only tested before an increment, and the carry bit out of a count's own "
           "sum (Pacing pulses judges both); a port whose value the count takes instead of the sum, or that picks which half it "
           "takes (a write: Access command fields and the data's piece judge them); an operand of a product or quotient that is "
           "not a count (Operation selectors (b) and Working values judge them).")
K14 = {"title": "Count increment inputs",
       "P1": "- Count increment inputs.\n  " + K14_SCOPE + "\n  " + K14_CRIT + "\n  " + K14_EXC + "\n  "
             "Outcome: it carries the increment into the count, so the count's value depends on it as on an operand. It is part of "
             "the count's piece, and the port is where the increment enters the entity holding the count: list it under \"Enters "
             "Through\" of the count's concept (for a child entity's port, as the closed set names it), although Pacing pulses "
             "names an input port letting a tick or count advance and step 3 would fold a pulse into what it times.\n  "
             "Evidence: cite the line adding it as a held line of the count's concept, and the port-map line wiring it as an entry "
             "line.",
       "P2": "- Count increment inputs.\n  " + K14_SCOPE + "\n  " + K14_CRIT + "\n  " + K14_EXC + "\n  "
             "Outcome: the port carries the count's increment into the entity holding the count (2.2: explicit flow; 2.6: the input "
             "port setting it): name it in step 3 at the block adding it and label it primary for the count's conceptual asset, "
             "although the pacing-pulses sentences bar a tick letting a count advance (this port is a term of the sum, not a tick) "
             "and although 2.7 would make it a secondary. The unit signal wired to it through the port map keeps its own label."}

META = {
    "K11": {"kind": "keep", "basis_kind": "step 1 (a response signalled by another module) + step 2 + 2.6 (the input port setting a decision)",
            "intended_cases": ["neorv32_cpu_control:alu_cp_done_i", "neorv32_cpu_control:lsu_wait_i"],
            "must_spare": [], "expected_harm": [], "placed_after": "Pacing pulses"},
    "K12": {"kind": "keep", "basis_kind": "step 1 (a request or response signalled to or from another module) + 2.6 boundary clause",
            "intended_cases": ["neorv32_slink:slink_rx_valid_i", "neorv32_slink:slink_tx_ready_i", "neorv32_slink:slink_rx_ready_o", "neorv32_slink:slink_tx_valid_o"],
            "must_spare": ["neorv32_slink:rx_fifo.we", "neorv32_slink:tx_fifo.re", "neorv32_slink:tx_fifo.avail", "neorv32_slink:rx_fifo.free"],
            "expected_harm": [], "placed_after": "Port buffers (c)"},
    "K13": {"kind": "keep", "basis_kind": "step 2 (a lock) + 2.6 (the element making a decision); Sequencing state's own lock exception",
            "intended_cases": ["neorv32_debug_dm:dm_ctrl.busy"],
            "must_spare": [], "expected_harm": [], "placed_after": "Sequencing state"},
    "K14": {"kind": "keep", "basis_kind": "2.2 explicit flow + 2.6 (the input port setting the value); Pacing pulses' own exclusion; one reference case",
            "intended_cases": ["neorv32_cpu_counters:inc_i"],
            "must_spare": [], "expected_harm": [], "placed_after": "Pacing pulses (after K11)"},
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    texts = {"K11": K11, "K12": K12, "K13": K13, "K14": K14}
    shapes = HERE / "meta_v9h_shapes.json"            # must-spare and expected-harm lists from the k1_shapes workflow, if written
    meta = {k: dict(v) for k, v in META.items()}
    if shapes.exists():
        for rid, add in json.loads(shapes.read_text(encoding="utf-8")).items():
            for key in ("must_spare", "expected_harm", "intended_cases"):
                if add.get(key):
                    meta[rid][key] = sorted(set(meta[rid].get(key, [])) | set(add[key]))
            if add.get("basis"):
                meta[rid]["basis"] = add["basis"]
    tmp = HERE / "_check_v9h.json"
    tmp.write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(HERE.parent / "check_new_rules.py"), str(tmp)], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-2500:])
    tmp.unlink()
    if r.returncode:
        sys.exit("checker BLOCKERS: nothing written")
    (HERE / "rule_texts_v9h.json").write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "meta_v9h.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    for rid, t in texts.items():
        print(f"{rid} {t['title']:24} P1 {len(t['P1'].split()):4} words  P2 {len(t['P2'].split()):4} words")
    print("written rule_texts_v9h.json, meta_v9h.json")


if __name__ == "__main__":
    main()
