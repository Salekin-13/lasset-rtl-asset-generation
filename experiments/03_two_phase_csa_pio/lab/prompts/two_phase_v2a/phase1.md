THIS CALL: PHASE 1, CONCEPTUAL ASSETS

Name each unit's conceptual assets. Do not label RTL elements primary or secondary; Phase 2 does that.

For each UNIT of the diagram:

1. Interface. Looking only at the unit's INPUTS and OUTPUTS, name the information it takes in and produces: data received, held or returned; settings and configuration; state and status; commands, requests and their responses; events signaled to other modules. Check in the RTL what each input is for and each output carries.

2. Inside. Name held state the unit's behavior depends on and no port shows directly: a mode, a lock, a count, a stored setting, a state machine's state. Also name each enable, select, override or lock deciding whether other information is used, passes or may change: such a decision is information of its own.

3. Merge and split. Information that always travels together for the same use, or repeats per index or per port of one role, is one piece. Information with different uses is separate, even on a shared port. An internal signal only timing one step of other information (an increment pulse, a started flag, a one-cycle request) is part of what it times, not a decision of its own.

4. Rubric. For each piece, answer each question below "yes" only when both its parts hold: first, a judgement of what the information is, from what the RTL does with it, assuming the question's objective (section 3); second, a mechanism that the RTL shows (cite the lines) or the black-box rule (section 1) gives.
   Confidentiality. Assume the IP is to be integrated into an IC where confidentiality protections are required. Is this information, received as input or generated inside the IP, something an integrator may consider secret? If so, can an element of the IP leak or expose it? The second part holds when an element holds or carries it where it is observable at the integration level: an output port, a read-back, a debug or test path, a status depending on it, a shared structure, or data-dependent timing (4.4). A designed use does not make this part "no": Phase 2 judges authorization.
   Integrity. Assume the IP is to be integrated into an IC where integrity protections are required. Is this information material an integrator may deem sensitive, or a state or configuration setting that needs to be immutable during certain operations or modes? If so, can an element of the IP modify it?
   Availability. Does this information gate (enable, block or select) an output port or the use of an input port, or would the IP or the IC stop working without it? Clock and reset inputs, and chains only synchronizing or releasing a reset, do not qualify; a setting or request controlling a clock (an enable, a rate) does. If so, can an element of the IP block, disable or withhold it? Count only integration-level denial of service: a blocked port, a lost required transfer, or a halted IP or IC.
   Undermined expected behavior. Is this information something that a privileged mode, an override, a bypass, test-packet injection or a similar behavior at the integration level acts on? If so, can that behavior make the IP produce incorrect output, or stop its function, under normal operation? Focus on what may be compromised.

5. Keep. Keep a piece as a conceptual asset when any question is "yes" AND it passes the asset test (2.3): you can name the objective at risk and a plausible way an attacker could violate it. List the rest under "considered, not kept", with the reason.

6. Anchor. For each conceptual asset, list under "enters through" each unit port whose value is carried (2.2) into it, and under "leaves through" each unit port written by an element carrying it. Skip ports that only decide it or whose value it only decides. Write ports as INPUTS and OUTPUTS do, or as the closed-set field when only one field of a record port carries it. Information produced inside the unit has no entry port; information used up there has no exit port. Cite the RTL lines where it enters ("entry lines"), is stored or produced ("held lines") and leaves ("exit lines"); Phase 2 starts from the held lines.

Rules:
- Describe a conceptual asset by what the information is, not by an element name.
- A diagram arrow shows a flow. It does not make the information an asset: decide from what the information is, and from the rubric.
- Clocks and resets. Clock and reset inputs, and chains only synchronizing or releasing a reset (a reset shift register, a registered copy of a reset), are not conceptual assets under any question. Settings or requests controlling a clock (an enable, a rate), and decisions triggering a reset (a timeout, a violation), are judged as usual.
- Build-time values. A generic or constant that only fixes the build (a feature switch, a size or depth, a fixed address or address map, a buffering choice) is not a conceptual asset: no element of the IP can change or withhold it at run time. Instead, name the run-time decision using it as its own concept (such as which port an address selects, or which requester is granted).
- Pacing pulses. A tick, edge pulse or divider count made inside the unit only to pace another step is part of that step or its rate setting (step 3), unless the unit outputs it.
- Forwarded transactions. A bus transaction (a request or response with its address, data and handshake) that the unit only forwards between its ports or to a sub-unit, without storing, computing or deciding it, is not a conceptual asset of this unit. The decision whether or where it passes is judged as usual.
- Bus handshake copies. A bus response acknowledge that only repeats or delays the bus request strobe, and a bus error flag tied to a constant, are not information of their own.
- Working values. Partial results inside a computation (a partial sum, product or round value, a synchronizer stage, a debiasing step) are part of the result they produce (step 3).

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
