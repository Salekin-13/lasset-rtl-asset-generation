THIS CALL: PHASE 1, CONCEPTUAL ASSETS

Name the conceptual assets of each unit. Do not label RTL elements as primary or secondary in this phase; Phase 2 does that.

Steps, for each UNIT of the diagram:

1. Interface. Look at the unit as a box with its INPUTS and OUTPUTS only. Name the information that goes into the unit and the information it produces as a result: data it receives, holds or returns; settings and configuration; state and status; commands, requests and their responses; events it signals to other modules. Use the RTL to see what each input is used for and what each output carries.

2. Inside. Name the state the unit holds that its behavior depends on, when no port shows it directly: a mode, a lock, a count, a stored setting, the state of a state machine. Name also each enable, select, override or lock that decides whether other information is used, passes or may change: such a decision is information of its own.

3. Merge and split. Two pieces of information that always travel together and serve the same use are one piece. The same information repeated per index, or per port of one role, is one piece. Information that serves different uses is separate, even when it shares a port. An internal signal that only times one step of other information (an increment pulse, a started flag, a one-cycle request) is part of the information it times, not a decision of its own.

4. Rubric. For each piece of information from steps 1 to 3, answer the four questions below. Each question has two parts. The first part is a judgement about what the information is; make it from what the RTL does with the information, assuming the question's objective as section 3 says. The second part asks for a mechanism; the RTL must show it (cite the lines), or the black-box rule of section 1 must give it. Answer "yes" only when both parts hold.
   Confidentiality. Assume the IP is to be integrated into an IC where confidentiality protections are required. Is this information, received as input or generated inside the IP, something an integrator may consider secret? If so, can an element of the IP leak or expose it? The second part holds when an element holds or carries the information where it can be observed at the integration level: an output port, a read-back, a debug or test path, a status that depends on it, a shared structure, or data-dependent timing (4.4). Whether that exposure is authorized is decided in Phase 2, so a designed use does not make this part "no".
   Integrity. Assume the IP is to be integrated into an IC where integrity protections are required. Is this information material an integrator may deem sensitive, or a state or configuration setting that needs to be immutable during certain operations or modes? If so, can an element of the IP modify it?
   Availability. Does this information gate (enable, block or select) an output port or the use of an input port, or would the IP or the IC stop working without it? A clock input, a reset input, or a chain that only synchronizes or releases a reset does not qualify; a setting or request that controls a clock (an enable, a rate) does. If so, can an element of the IP block, disable or withhold it? Count only integration-level denial of service: a blocked port, a lost required transfer, or a halted IP or IC.
   Undermined expected behavior. Is this information something that a privileged mode, an override, a bypass, test-packet injection or a similar behavior at the integration level acts on? If so, can that behavior make the IP produce incorrect output, or stop its function, under normal operation? Focus on what may be compromised.

5. Keep. Keep a piece of information as a conceptual asset when at least one question is "yes" AND it passes the asset test (2.3): you can name the objective at risk and a plausible way an attacker could violate it. List every other piece under "considered, not kept", with the reason.

6. Anchor. For each conceptual asset, give the unit ports where it enters and where it leaves. Write a port as INPUTS and OUTPUTS write it, or write the field the closed set lists when only one field of a record port carries the information. List a port under "enters through" when its value is carried (2.2) into the information, and under "leaves through" when an element that carries the information is written to it. A port that only decides the information, or whose value the information only decides, is not listed. Information produced inside the unit has no entry port; information used up inside the unit has no exit port. Cite the RTL lines that show it entering ("entry lines"), being stored or produced ("held lines") and leaving ("exit lines"). The held lines tell Phase 2 where to start.

Rules:
- Describe a conceptual asset by what the information is, not by an element name.
- An arrow in the diagram says that a flow exists. It does not make the information an asset: decide from what the information is, and from the rubric.
- Clocks and resets. A clock input, a reset input, and a chain that only synchronizes or releases a reset (a reset shift register, a registered copy of a reset) are not conceptual assets under any question. A setting or request that controls a clock (an enable, a rate), and a decision that triggers a reset (a timeout, a violation), are judged as usual.
- Build-time values. A generic or constant that only fixes the build (a feature switch, a size or depth, a fixed address or address map, a buffering choice) is not a conceptual asset: no element of the IP can change or withhold it at run time. Name the run-time decision that uses it as its own concept instead (for example, which port an address selects, or which requester is granted).
- Pacing pulses. A tick, edge pulse or divider count made inside the unit only to pace another step is part of that step or of its rate setting (step 3), unless the unit outputs it.
- Forwarded transactions. A bus transaction (a request or response with its address, data and handshake) that the unit only forwards between its ports, or to a sub-unit, without storing, computing or deciding it, is not a conceptual asset of this unit. The decision about whether or where it passes is judged as usual.
- Bus handshake copies. A bus response acknowledge that only repeats or delays the bus request strobe, and a bus error flag tied to a constant, are not information of their own.
- Working values. The partial results inside a computation (a partial sum, product or round value, a synchronizer stage, a debiasing step) are part of the result they produce (step 3), not concepts of their own.

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
  {"unit": "<the UNIT's entity name>", "concept": "<short name of the information>", "reason": "<one sentence: which part of which question failed, or which part of the asset test; or 'merged into Cn'>"}
 ],
 "notes": ["<one sentence each: an RTL fact that contradicts the closed set or the diagram, with its line>"]
}
Number the ids C1, C2, ... across the whole module.
"objectives" lists the objectives at risk. Each comes from a "yes": confidentiality gives C, integrity gives I, availability gives A, and undermined expected behavior gives the objective the behavior breaks (I when it makes the output incorrect, A when it stops the function).
