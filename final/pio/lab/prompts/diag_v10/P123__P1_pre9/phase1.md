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
- Clocks and resets (a).
  Scope: any unit.
  Criteria: (1) any of: a clock or reset input (tagged so, or only wired into instances); a reset request (one reaching a reset chain or reset output port; a FIFO or buffer clear is not one) that this unit only combines, gates, registers or passes on to such a chain or port (every element it gives value to or decides), the input port bringing it in (never a bus data port or field), its copies (its value unchanged) or any reset output port; a chain only synchronizing or releasing a reset, giving value only to its next stage or a reset output port (a reset shift register, a registered reset copy); (2) not the record of a reset's cause, a compare outcome that restarts a counter, or, unless (c) bars it, a decision triggering a reset (a timeout) where it is computed (not a copy).
  Outcome: not conceptual assets under any question.
  Evidence: Do not cite their lines as held lines.
- Clocks and resets (b).
  Scope: any unit.
  Criteria: (1) a serial link's clock line (the unit port itself, to or from a peer device) or a setting or decision whose only use, apart from a read-back, is to drive or shape that line (polarity, phase against the data, holding it while the peer stretches it), including when, apart from its read-back, its counterparts show it gives value to or decides only the element driving that line, which gives value to or decides nothing but the line, even where the line's phase sets when the peer samples or sends data; (2) not the link's data or select line, its rate setting (how often the line toggles) or the unit's clock-enable output.
  Outcome: keep no concept for it and do not cite its lines as held lines; a transfer-mode, format or rate concept holding other settings stays, without it.
- Clocks and resets (c).
  Scope: a decision that a write was refused or carried a wrong value (a write while locked, a wrong password), its gated or registered copies, or a setting choosing only whether such a violation resets.
  Criteria: (1) apart from a read-back, it gives value to or decides at least one element, and every one is a reset request (as in (a)) or the record of that reset's cause; (2) not the cause record, the lock refusing the write, or a compare outcome that restarts a counter.
  Outcome: not conceptual assets, although step 3 makes a compare of a written value with a fixed value a piece.
- Build-time values. A generic or constant only fixing the build (a feature switch, size or depth, fixed address or address map, buffering choice) is not a conceptual asset: no element of the IP can change or withhold it at run time. Nor is a run-time bit that a statement ANDs with a build-time switch and whose effect includes writing characters to a file or the screen (a simulation-only mode), although a bus write can change it: it is part of that build choice and is not the run-time decision the next sentence asks for. Instead, name the run-time decision using it as its own concept (which port an address selects, which requester is granted).
- Pacing pulses.
  Scope: A tick, edge pulse or divider count made inside the unit, or an input port used only as a condition letting a tick or count meeting (1) advance.
  Criteria: (1) only to pace another step.
  Exceptions: if it is a pulse an output port carries (2.2) (not a port the pulses only decide or time); an enable deciding whether the count runs at all; a request held until served; a start pulse, or its copy, decoded from a received command or access; a count whose compare with a limit raises a reset, error or interrupt, or sets an output level; a step counter (sequencing state, below, judges it).
  Outcome: part of that step or its rate setting (step 3). Do not name it in any concept's information or cite its lines as held lines.
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
- Second copies.
  Scope: an internal register (not a port).
  Criteria: (1) that directly copies bits, not as an index; (2) of one other register of its own entity; (3) whose other assignments write only constants; (4) that no condition reads.
  Outcome: it is a copy kept only while the value moves (2.6), not a piece of its own: name its information under the copied bits' piece, and do not cite its lines as held lines.
- Bus handshake copies (a).
  Scope: A bus response acknowledge, and a bus error flag.
  Criteria (any of): (1) the acknowledge only repeating or delaying the bus request strobe; (2) the error flag tied to a constant.
  Exceptions: an acknowledge also gating what a read returns.
  Outcome: are not information of their own.
- Bus handshake copies (b).
  Scope: In a unit passing bus requests from an input bus request port to an output one, a register of one bit, or one bit per requester, not a request waiting for a grant (a rule below).
  Criteria: (1) every assignment to it (directly or through its next-value signal), apart from clearing or holding it, copies or ORs in only the strobe, lock bit or response error bit of the access in progress, or sets it when a test reading only that access's fields and build-time values holds (a route bit); (2) the unit reads it only to start, pass on, route, time or end that access, the access it serves or that locked sequence, or to drop words that access fetched.
  Exceptions: the grant, its select and strobe; an address decode choosing which of several output bus request ports gets the access; a pending fence or flush clearing what the unit stores; a busy flag set when the unit itself issues an access; a timeout count, its error and its suppression flag; a reservation; a software-set lock guarding later accesses (not a copied lock bit); a read enable deciding whether stored data leaves on the response; and a cache's hit.
  Outcome: holds no information of its own: the register only re-times a value the access already carries. It is not a piece of its own, although steps 1 to 4, Build-time values and 4.4 would name it a request, status, lock, select, compare or bypass, and even where another rule judges a decision or held request as usual. A compare or decode reading a register this rule bars, and otherwise only that access's own fields and build-time values, or used only to set such a register, is part of that register (step 3), not a piece of its own. Keep no concept for them and cite none of their lines as held lines, except a line also assigning an element this rule does not bar.
- Bus handshake copies (c).
  Scope: A one-bit register.
  Criteria: (1) that one unconditional statement sets on every clock edge to a stored state bit or flag of this unit, copied or inverted and ANDed only with terms saying when it applies (a request strobe, its read or write bit, an operation-type decode); (2) that only a bus response's acknowledge or data fields read.
  Exceptions: that state, where held; a register set only from the unit's input ports (a read enable from a strobe and a read or write bit); and a flag that a condition sets to a constant (a timeout error raised at a count's limit).
  Outcome: only re-times that state to the response. It is part of that state, not a piece of its own, although step 1 names status and responses and step 3 makes a compare of stored state with a request a piece: keep no concept for it and do not cite its lines as held lines.
- Working values (a).
  Scope: inside a computation.
  Criteria (any of): (1) a partial sum, product or round value; (2) a debiasing step with its state and flag, although step 2 would call them a decision.
  Exceptions: judged as usual: the finished result, even an instance output, held where computed or an output port takes it from; a count.
  Outcome: partial results are part of the result they produce (step 3), not concepts of their own.
- Working values (b).
  Scope: a synchronizer stage.
  Criteria: a register only shifting in one unit input port's bit, apart from constants.
  Outcome: do not name it in any concept's information or cite its lines as held lines.
- Slices.
  Scope: a signal (not a port).
  Criteria: (1) its assignments (each line), leaving out only its reset assignment and constants in another generate branch, each take only slices or indexed bits (never the whole element) of one element, the same in every line (one closed-set entry: for a record, one field), alone or concatenated (side by side, with no constant, not combined by a logic or arithmetic operator), even through signals; (2) the element the bits come from is not a bus request or response record port, a field of one, or a write's data.
  Outcome: it only carries that element's value (2.2) and is not a piece of its own: do not cite its lines as held lines.
- Hand-offs.
  Scope: check each port-map line where an instance's non-record output port drives a signal another instance or this unit's logic reads; a wait, fault or write-enable flag, or an access address.
  Criteria: that one instance outputs on a non-record port to another instance or this unit's logic.
  Exceptions: a field of a record an instance outputs on a record port is never a hand-off, even wired alone into another instance's non-record port; if Port buffers covers it, then this rule does not apply.
  Outcome: a hand-off: its own piece (step 2). No step-3 clause or other rule folds it, even when it travels with the data it qualifies, when another instance outputs the same address earlier or later (cite each output's port-map line, in one piece), or when it is one bit of a count: then hold it at the line assigning that bit to the instance output, and a count kept only to make it belongs to this piece.
  Evidence: if the RTL cannot show which kind it is, judge from the port names at either end and say so.
- Access command fields (a).
  Scope: Accesses on a record port (never on non-record ports, even ones together carrying an access) addressing this unit's own registers, FIFOs, locks or memory words (not a cache's copies).
  Criteria (any of): (1) the fields only saying whether an access happens, its direction and which register, FIFO or bytes it reaches (a strobe, a read or write bit, register-select address bits, byte enables; an address indexing a memory's stored words is the access address, not one of them); (2) a write enable whose assignment reads only these fields and that only lets a register or FIFO take the written data.
  Exceptions: Not covered: a request held until served, a select routing it on, and a strobe driven on to a unit output port other than as an acknowledge; an operation's start pulse (not an access's strobe or write enable).
  Outcome: they are part of the information the access writes or reads, not information of their own; such a field whose value a register takes as its new content belongs to that register's piece. They are not pieces of their own, although steps 1 and 2, Build-time values and Per-region checks would keep some: keep no concept for them.
  Evidence: cite no line only testing them, or only assigning such a write enable, as a held line.
- Access command fields (b).
  Scope: A signal of its own decoded from these fields.
  Criteria (any of): (1) gates or masks what a read returns (a read enable, a select also masking read data); (2) pops a FIFO of data the unit generates itself.
  Exceptions: An inline condition is no such signal, nor is a strobe of a FIFO that Port buffers covers.
  Outcome: it is its own piece (step 2): name it by what it decides; no step-3 clause folds it.
  Evidence: hold it at the line assigning it.

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
