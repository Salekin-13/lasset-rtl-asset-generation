THIS CALL: PHASE 1, CONCEPTUAL ASSETS

For each UNIT of the diagram:

1. Interface. Name information entering or leaving through the unit's INPUTS and OUTPUTS: data received, held or returned; settings and configuration; state and status; commands, requests and responses; events signaled to other modules.

2. Inside. Name state the unit holds that its behavior depends on and no port shows directly: a mode, a lock, a count, a stored setting, a state machine's state. Also name each enable, select, override or lock deciding whether other information is used, passes or may change: such a decision is information of its own. Neither sentence covers sequencing state outside a coprocessor (a rule below).

3. Merge and split. Information that always travels together for the same use, or repeats per index or per port of one role, is one piece. Information with different uses is separate, even on a shared port. An internal signal only timing one step of other information (an increment pulse, a started flag, a one-cycle request) is part of what it times, not its own decision. A compare of stored state with a request, a count with a stored limit, or a written value with a fixed value, whose result picks or triggers what happens next, is its own piece (step 2), even when it lasts one cycle. Hold it where computed; never merge it into its inputs or the action it triggers. Any other compare, decode or gate is judged by step 2 and the timing clause. A tick only pacing a step is a pacing pulse; a compare only picking a computation's result (a minimum or maximum) is a working value.

4. Rubric. Per piece, answer each question "yes" only when both parts hold: first, what the information is, judged from what the RTL does with it; second, a mechanism the RTL shows or the black-box rule (section 1) gives.
   Confidentiality. Assume the IC integrating the IP requires confidentiality protections. Is this information, received as input or generated inside the IP, something an integrator may consider secret? If the first part holds, can an element of the IP leak or expose it by holding or carrying it where the integration level can observe it: an output port, a read-back, a debug or test path, a status depending on it, a shared structure, or data-dependent timing (4.4)? Phase 2 judges authorization, so a designed use never makes the second part "no".
   Integrity. Assume the IC integrating the IP requires integrity protections. Is this information material an integrator may deem sensitive, or a state or configuration setting that must be immutable during certain operations or modes? If the first part holds, can an element of the IP modify it?
   Availability. Does this information gate (enable, block or select) an output port or an input port's use, or would the IP or IC stop working without it? If the first part holds, can an element of the IP block, disable or withhold it, so that a port is blocked, a required transfer is lost, or the IP or IC halts?
   Undermined expected behavior. Does a privileged mode, an override, a bypass, test-packet injection or similar integration-level behavior act on this information? If the first part holds, can that behavior make the IP produce incorrect output, or stop its function, under normal operation? Focus on what may be compromised.

5. Keep. Keep a piece as a conceptual asset when any question is "yes" AND it passes the asset test (2.3); list the rest under "Not Kept". Phase 2 sees only kept concepts, starting from their held lines.

6. Anchor. Under "Enters Through" list each unit port whose value is carried (2.2) into the information; under "Leaves Through", each unit port written by an element carrying it; either may be empty. Skip ports that only decide the information or that it only decides. When a state machine, apart from reset, changes state only at steps a peer device's clock paces, and its next state depends only on its current state and one bit of a non-record input port (directly or through synchronizer stages), that port, never the peer's clock line, is the input port setting the state (2.6), though only conditions test its bit (an implicit flow, 2.2). List that port under "Enters Through" of the concept holding that state; the skip above does not apply to it. Write ports as INPUTS and OUTPUTS do, or as the closed-set field when one field of a record port alone carries the information.

Rules:
- Describe a conceptual asset by what the information is, not an element name. A diagram arrow shows a flow, not an asset.
- Precedence. A rule's bar is its sentence saying information is not a conceptual asset or not a piece of its own. What a rule judges as usual or does not cover is spared only from that rule's bar.
- Reading a rule. Check its scope, then each criterion, then each exception it lists, in that order, against the RTL; where a criterion says "only", "every" or "one element", check every assignment or use, not one. Its outcome follows only for an element in scope that meets every criterion (one, where marked "any of") and that no listed exception covers.
- Forwarded transactions (a).
  Scope: A bus transaction (a request or response with its address, data and handshake).
  Criteria (any of): (1) that the unit only forwards between its ports or to a sub-unit, without storing, computing or deciding it; also forwarding: (2) merging several ports' bus responses into one (an OR or a multiplexer); (3) a register stage passing a whole request or response record on unchanged a cycle later, although it stores the record; (4) a record this unit only wires between one of its ports and the port map of an instance of another IP, with no statement of this unit reading or writing it (a constant tied to it in a generate branch lacking the instance is no such statement), even though the black-box rule lets the instance change it.
  Exceptions: a bus whose address this unit drives on a non-record output port of its own and whose acknowledge it takes on a non-record input port of its own: the request it drives onto that bus's ports and the response it takes from them are judged as usual, as information leaving and entering the unit there; the decision whether or where the transaction passes; a transfer's address and direction; a wait or fault flag; an interrupt or debug request; a register read-back word, and the register contents an instance other than a buffer or register stage holds; an arithmetic, logic or compare result an instance computes from operands; the value a mixing statement writes (such as the value written back to a register), unless that statement mixes only relayed data, bus responses and constants; and data the unit stores (not a register stage's copy), shifts through its own register, generates or computes from, even when a buffer instance also holds it.
  Outcome: is not a conceptual asset of this unit.
  Evidence: judge from port names which ports are that bus's address, acknowledge and other lines, and say so.
- Forwarded transactions (b).
  Scope: Relayed data is data a transfer carries into or out of the unit (data loaded or stored, instruction words fetched, messages received or sent).
  Criteria: (1) no statement of this unit stores it or computes from it; (2) it only moves between unit ports, between a unit port and an instance of another IP, between such instances, through a register stage, or into a statement only mixing it with other values (an OR, a multiplexer).
  Exceptions: those of (a).
  Outcome: Relayed data, alone or with only the acknowledge and ready lines timing its transfer, is not a piece of its own, even in a unit executing instructions and although step 1 names data received or returned and 4.2 end-user's private data: keep no concept for it.
  Evidence: Judge from port names which instance ports carry relayed data and which a computed result, and say so.
- Instance-driven records. A record driven whole by one instance of another IP and wired whole into one or more other instances' port maps (decoded controls or fetch results between sub-units; closed set: the record's own entry gets its value from one instance port and gives it only to instance ports) holds nothing of this unit, even if a port map also takes a field alone, a statement of this unit reads one, or it carries the instructions this unit executes: that instance holds each value; the record and its fields, one-bit flags included, only carry copies, and none is a non-record signal. So information such a record or its fields carry, and that no other element except bus request or response record ports stores, computes or passes whole across the boundary (2.6; an instance output carrying it only by the black-box rule does not count), is not a piece of this unit, although step 2 names a state machine's state and each enable, and 2.4 and 4.2 the privilege mode and program counter: keep no concept for it. Information a non-record unit input port itself brings in crosses the boundary whole at that port (2.6), even when the port is wired straight into that instance: list the port under "Enters Through" and hold the information at the line wiring the port. An element this unit's statements compute from such a field and other values keeps no concept about that field alive. Cite no declaration or port-map line of such a record or its fields as a held line. Judged as usual: non-record signals handed between instances; non-record unit ports, even one wired straight into an instance (a debug or interrupt request line); records this unit's statements set, whole or per field; records whose fields port maps or several instances set separately; and, for its other values, an element this unit's statements compute from such a field and other values.
- Register read-back. In a unit executing instructions, the word an instance outputs for reads of its control and status registers, when a statement of this unit merges it directly into the value written back to a register, is its own piece: those registers' contents as software reads them. Hold it at that instance output; no step-3 clause or other rule folds it. In a unit executing instructions, a word that an instance outputs for reads of its own control and status registers, and that this unit reads only in an OR into the word another instance takes in to answer such reads, only carries those registers to the other instance's read-back: the registers (a count, a protection setting, a configuration or status bit) stay inside the first instance, and no statement of this unit stores, computes or decides them (a constant tied to the word in a generate branch lacking that instance is no such statement). So these words (that word and the one the OR makes) and those registers are not pieces of their own, although step 2 names a count and a stored setting and 2.4 a memory-protection configuration: keep no concept for them, as the read-back piece covers those registers as software reads them; cite no line of these words as a held line, nor, for the read-back piece, a port-map line feeding the first instance. Judge from port names (section 1's second exception) which outputs and inputs this rule names, and say so. Judged as usual: the read-back's instance output, the value written back to a register, and the first instance's other outputs (a wait or fault flag, a result, an access address, a unit output port it drives), even when computed from those registers.
- Operation selectors (a).
  Scope: In a unit executing an instruction or atomic memory operation a processor issues to it (a coprocessor, an atomic read-modify-write).
  Criteria (any of): (1) instruction or request fields only picking the operation or the result form returned (an opcode, a function code, an instruction-type bit); (2) their stored copies; (3) flags decoded from them only naming the operation.
  Exceptions: (1) Judged as usual: a start command or pulse saying when the operation starts, even one decoded per operation (a multiply or divide start), a register access's address and write enable, a completion flag, and a setting decoded from them that changes how operands are read (signedness). (2) A plain bus read or write, its read or write bit and a read enable made from it are not covered.
  Outcome: they are part of that operation (step 3), not pieces of their own, although step 2 names a select.
  Evidence: Do not list them under "Enters Through" or cite their lines as held lines, except a line assigning an element this rule judges as usual.
- Operation selectors (b).
  Scope: In a unit executing an instruction or atomic memory operation a processor issues to it, a register.
  Criteria: (1) whose value, apart from constants and itself, comes only from one source operand input (a port or a request-record field, not of a bus request (2.6)) when the operation starts, directly or through its next-value wire; (2) reaches an output port only through the element holding the result.
  Outcome: it only holds that operand while the operation uses it (2.6: a copy kept only while the value moves). It and its next-value wire are part of that operand's piece: keep that piece, list the operand input under "Enters Through".
  Evidence: cite the lines where it takes the operand as entry lines; do not cite them as held lines.

OUTPUT

Return one JSON object:
{
 "IP": "<the module name given in the input>",
 "Conceptual Assets": [
  {
   "Concept ID": "C1",
   "Concept Name": "<short name of the information>",
   "Unit": "<the UNIT's entity name>",
   "Information": "<one or two sentences: what the information or state is, and which use of the IP depends on it; if it has no entry port and no exit port, say why>",
   "Rubric": {
    "Confidentiality": "yes" | "no",
    "Integrity": "yes" | "no",
    "Availability": "yes" | "no",
    "Undermined Expected Behavior": "yes" | "no"
   },
   "Rubric Reason": "<for each yes, one sentence: the judgement and the mechanism, with line numbers>",
   "Objectives At Risk": ["C" | "I" | "A", ...],
   "Attack": "<one sentence: a plausible way an attacker could violate these objectives>",
   "Enters Through": ["<port or port field>", ...],
   "Leaves Through": ["<port or port field>", ...],
   "Entry Lines": [<RTL line numbers where it enters>],
   "Held Lines": [<RTL line numbers where it is stored or produced>],
   "Exit Lines": [<RTL line numbers where it leaves>]
  }
 ],
 "Not Kept": [
  {
   "Candidate Name": "<short name of the information>",
   "Candidate Unit": "<the UNIT's entity name>",
   "Merged Into": "<the kept Concept ID it was merged into, or an empty string>",
   "Why Not Kept": "<one sentence: which part of which question failed, or which part of the asset test; an empty string for a merged piece>"
  }
 ],
 "Notes": ["<one sentence each: an RTL fact that contradicts the closed set or the diagram, with its line>"]
}
Follow this format strictly: write every key shown, spelled and ordered as shown, in every object, and no other key. Each object starts with its own identifier: "Concept ID" in a conceptual asset, "Candidate Name" in a not-kept entry.
Number the Concept IDs C1, C2, ... across the whole module.
Each objective in "Objectives At Risk" comes from a "yes": confidentiality gives C, integrity gives I, availability gives A, and undermined expected behavior gives the objective the behavior breaks (I when it makes the output incorrect, A when it stops the function).
