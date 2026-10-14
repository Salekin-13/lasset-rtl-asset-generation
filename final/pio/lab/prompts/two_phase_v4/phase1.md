THIS CALL: PHASE 1, CONCEPTUAL ASSETS

Steps, for each UNIT of the diagram:

1. Interface. Name the information that enters or leaves the unit through its INPUTS and OUTPUTS: data it receives, holds or returns; settings and configuration; state and status; commands, requests and their responses; events it signals to other modules.

2. Inside. Name the state the unit holds that its behavior depends on, when no port shows it directly: a mode, a lock, a count, a stored setting, the state of a state machine. Name also each enable, select, override or lock that decides whether other information is used, passes or may change: such a decision is information of its own.

3. Merge and split. Pieces that always travel together and serve the same use are one piece, as is the same information repeated per index or per port of one role. Information that serves different uses is separate, even when it shares a port. An internal signal that only times one step of other information (an increment pulse, a started flag, a one-cycle request) is part of the information it times, not a decision of its own. A compare of stored state with a request, a count with a stored limit, or a written value with a fixed value, whose result picks or triggers what happens next, is its own piece (step 2), even when it lasts one cycle. Hold it where it is computed; never merge it into its inputs or the action it triggers. Any other compare, decode or gate is judged by step 2 and the timing clause. A tick that only paces a step is a pacing pulse, and a compare that only picks a computation's result (a minimum or maximum) is a working value.

4. Rubric. Answer four questions per piece. Each has two parts: first, a judgement of what the information is, from what the RTL does with it; second, a mechanism that the RTL shows or the black-box rule (section 1) gives. Answer "yes" only when both parts hold.
   Confidentiality. Assume the IP is to be integrated into an IC where confidentiality protections are required. Is this information, received as input or generated inside the IP, something an integrator may consider secret? If the first part holds, can an element of the IP leak or expose it, by holding or carrying it where the integration level can observe it: an output port, a read-back, a debug or test path, a status that depends on it, a shared structure, or data-dependent timing (4.4)? Phase 2 judges authorization, so a designed use does not make the second part "no".
   Integrity. Assume the IP is to be integrated into an IC where integrity protections are required. Is this information material an integrator may deem sensitive, or a state or configuration setting that needs to be immutable during certain operations or modes? If the first part holds, can an element of the IP modify it?
   Availability. Does this information gate (enable, block or select) an output port or the use of an input port, or would the IP or the IC stop working without it? If the first part holds, can an element of the IP block, disable or withhold it, so that a port is blocked, a required transfer is lost, or the IP or IC halts?
   Undermined expected behavior. Is this information something that a privileged mode, an override, a bypass, test-packet injection or a similar behavior at the integration level acts on? If the first part holds, can that behavior make the IP produce incorrect output, or stop its function, under normal operation? Focus on what may be compromised.

5. Keep. Keep a piece as a conceptual asset when at least one question is "yes" AND it passes the asset test (2.3); list every other piece under "considered, not kept". Phase 2 sees only kept concepts and starts from their held lines.

6. Anchor. List under "enters through" each unit port whose value is carried (2.2) into the information, and under "leaves through" each unit port that an element carrying the information is written to; either list may be empty. A port that only decides the information, or that the information only decides, is not listed. Write ports as INPUTS and OUTPUTS write them, or as the closed-set field when one field of a record port alone carries the information.

Rules:
- Describe a conceptual asset by what the information is, not by an element name. A diagram arrow shows a flow, not an asset.
- Clocks and resets. A clock input, a reset input, and a chain that only synchronizes or releases a reset (a reset shift register, a registered copy of a reset) are not conceptual assets under any question. A setting or request that controls a clock (an enable, a rate), and a decision that triggers a reset (a timeout, a violation), are judged as usual.
- Build-time values. A generic or constant that only fixes the build (a feature switch, a size or depth, a fixed address or address map, a buffering choice) is not a conceptual asset: no element of the IP can change or withhold it at run time. Name the run-time decision that uses it as its own concept instead (for example, which port an address selects, or which requester is granted).
- Pacing pulses. A tick, edge pulse or divider count made inside the unit only to pace another step is part of that step or of its rate setting (step 3), unless the unit outputs it. Do not name it in any concept's information or cite its lines as held lines. A request held until it is served, a start pulse decoded from a received command, and a step counter are not pacing pulses.
- Forwarded transactions. A bus transaction (a request or response with its address, data and handshake) that the unit only forwards between its ports, or to a sub-unit, without storing, computing or deciding it, is not a conceptual asset of this unit. Merging the bus responses of several ports into one (an OR or a multiplexer) is still forwarding. So is a record that this unit only wires between one of its ports and the port map of an instance of another IP, with no statement of this unit reading or writing it; in a unit that executes instructions, this does not cover the instructions it executes or the data it loads and stores. The decision about whether or where it passes is judged as usual.
- Bus handshake copies. A bus response acknowledge that only repeats or delays the bus request strobe, and a bus error flag tied to a constant, are not information of their own.
- Working values. The partial results inside a computation (a partial sum, product or round value, a synchronizer stage, a debiasing step) are part of the result they produce (step 3), not concepts of their own. Do not name a synchronizer stage in any concept's information or cite its lines as held lines.
- Hand-offs. A wait or fault flag, a write-enable flag, or an access address that one instance outputs on a port that is not a record and hands to another instance or to this unit's logic is its own piece (step 2). No step-3 clause or other rule folds it, even when it travels with the data it qualifies.

OUTPUT

Return one JSON object:
{
 "module name": "<the module name given in the input>",
 "conceptual assets": [
  {
   "id": "C1",
   "unit": "<the UNIT's entity name>",
   "concept": "<short name of the information>",
   "information": "<one or two sentences: what the information or state is, and which use of the IP depends on it; if it has no entry port and no exit port, say why>",
   "rubric": {"confidentiality": "yes" | "no", "integrity": "yes" | "no", "availability": "yes" | "no", "undermined expected behavior": "yes" | "no"},
   "rubric reason": "<for each yes, one sentence: the judgement and the mechanism, with line numbers>",
   "objectives": ["C" | "I" | "A", ...],
   "attack": "<one sentence: a plausible way an attacker could violate these objectives>",
   "enters through": ["<port or port field>", ...],
   "leaves through": ["<port or port field>", ...],
   "entry lines": [<RTL line numbers where it enters>],
   "held lines": [<RTL line numbers where it is stored or produced>],
   "exit lines": [<RTL line numbers where it leaves>]
  }
 ],
 "considered, not kept": [
  {"unit": "<the UNIT's entity name>", "concept": "<short name of the information>", "reason": "<one sentence: which part of which question failed, or which part of the asset test; or 'merged into Cn', where Cn is a kept id>"}
 ],
 "notes": ["<one sentence each: an RTL fact that contradicts the closed set or the diagram, with its line>"]
}
Number the ids C1, C2, ... across the whole module.
"objectives" lists the objectives at risk. Each comes from a "yes": confidentiality gives C, integrity gives I, availability gives A, and undermined expected behavior gives the objective the behavior breaks (I when it makes the output incorrect, A when it stops the function).
