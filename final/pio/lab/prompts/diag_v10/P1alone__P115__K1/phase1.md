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
- Sequencing state.
  Scope: units other than a coprocessor, a unit shifting in random bits it generates, or a test or debug access port a peer's clock paces (say which, from its ports and entity); in them, a state machine's state register (a test of its own value picks its next value) or a bit counter, phase counter, word counter or step counter; never a port (even one its bits or flags decide), an enable or rate setting, or another element its steps load or drive (a chip-select register, an address).
  Criteria: (1) restarts with each transfer or operation the unit performs, not only when disabled or at its own limit (even if one bit copies an enable or a queued command picks the first step); (2) is read only to pick that transfer's next step, to time or gate its strobes, commands, shifts, loads, acknowledges and multiplexers or other sequencing state, or to point its address at the next word; (3) not a flag a request or command sets, held until that request or its locked sequence ends, however it ends; (4) not a reservation one access sets and a later one checks; (5) not the current grant (a state naming which requester holds a shared path) or the select and strobe it drives; (6) not a count, other than a transfer's bit counter, whose compare with a limit raises a reset, error or interrupt, or sets an output level, such as a timeout or timer count, nor that compare's flag or a timeout's suppression flag.
  Outcome: sequencing state: it only orders steps of information other elements hold, so it and its busy and done flags (below) are not information or pieces of their own, although step 2 names a state machine's state, a count and a select, and 2.4 control flow (a program's): keep no concept for them.
  Evidence: cite none of their lines as held lines, except one also assigning an element this rule does not bar.
  - Scope: in the same units, a flag, not a port.
    Criteria (any of): (1) a busy flag decoded from sequencing state alone (every element it gets value from or is decided by); (2) a done flag only sequencing state sets, at its last step (every line raising it, none a port map).
    Outcome: part of sequencing state (above).
  - Scope: a non-record unit input port.
    Criteria: (1) reaches the unit's logic only through synchronizer stages (registers only shifting that port's bit along, and wires only copying one of their bits) that give value to nothing but each other and decide nothing but a state machine's state register (list each stage's counterparts); (2) no conceptual asset holds that state; (3) not a clock, a reset or a serial link's clock line.
    Outcome: the port's bit is that peer's command to the state machine, information of its own whose primary is that port (2.6: the input port setting it), never that state register, which the bit only decides (2.2), nor those stages.
  - Scope: in a coprocessor, a count.
    Criteria: (1) a multi-cycle operation steps it every clock cycle of its busy state; (2) its end test only leaves that state.
    Outcome: a step counter, one piece of information with that state. Keep that state as a concept and hold the count in it, not in the operation's result or its pacing.

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
