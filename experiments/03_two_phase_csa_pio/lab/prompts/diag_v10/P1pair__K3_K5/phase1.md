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
- Build-time values. A generic or constant only fixing the build (a feature switch, size or depth, fixed address or address map, buffering choice) is not a conceptual asset: no element of the IP can change or withhold it at run time. Nor is a run-time bit that a statement ANDs with a build-time switch and whose effect includes writing characters to a file or the screen (a simulation-only mode), although a bus write can change it: it is part of that build choice and is not the run-time decision the next sentence asks for. Instead, name the run-time decision using it as its own concept (which port an address selects, which requester is granted).
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
- Memory access address. In a unit that is itself the store of a memory (an array it assigns on a clock edge, not a cache's copies), a wire whose only assignment copies or slices the address field of a bus request record port (closed set: role "index", and that field is its only "gets value from" partner) and whose value picks which word of that array an access writes or reads is a select (step 2) deciding which stored word the access uses or changes, so it is a piece of its own, the access address, even though the unit returns it on no output port and holds it in no register, and although Access command fields lists register-select address bits and byte enables, step 3 would merge it into the stored words or the access, and 2.2 calls its use an index flow (that flow carries the address into the word read; it does not make the address only a path to the stored words): a changed address makes the access write or return a word it was not aimed at, so judge its rubric by that mechanism, and hold it at the line assigning it (not its registered copy, which Held addresses bars).
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
- Per-region checks.
  Scope: the per-region or per-entry results.
  Criteria: the unit (1) makes the same compare or permission check per region or entry; (2) only combines the results (a priority chain, an OR) into one decision.
  Exceptions: a per-entry result itself picking where a request goes or which entry an access changes (which port an address selects, which lock is addressed) stays its own piece.
  Outcome: that decision is the piece, held where they combine; the results are its working values (step 3), although step 3 makes a compare of stored state with a request a piece.
- Arbitration bookkeeping. A register only remembering the previous grant for round-robin priority (not the current grant, its select and strobe, or a request held until served) holds no decision of its own: it only tilts the next grant. It is not a piece of its own, although step 2 names a select: keep no concept for it, nor cite its lines as held lines.
- Requests waiting for a grant. In a unit with a test choosing which of several requesters an output bus request port serves (it reads each requester's request strobe and assigns which one holds that port), a one-bit register per requester whose assignments, apart from reset and clearing it while that requester holds the port, only OR in that requester's request strobe, and that this test reads, stores a request taken and not yet served; the signal the grant's statements set that drives that port's strobe field decides whether an access passes on, not who holds the port: each is information of its own, apart from the grant, which the state register naming the holder and the select hold; this rule does not cover lock bits copied from the requests' lock fields or a register only remembering the previous grant. Step 3's timing clause and the rules on bus handshake copies, arbitration bookkeeping, sequencing state and pacing pulses do not cover such a register or that strobe signal: keep the waiting requests as one piece and the strobe signal as another, each apart from the grant, and cite every line assigning them as held lines, reset lines included.
- Processor context fields.
  Scope: A field, of a record input port other than a bus request or response record port (2.6).
  Criteria: (1) tells the processor's privilege mode, whether it is in debug mode or takes a trap, or whether the current access is a fetch or data access, read or write; (2) this unit reads it and only tests it (a condition, select, compare with a fixed value, gate on another result), directly or through a wire only selecting between such fields.
  Exceptions: (1) Judged as usual: the decision such a field refines, where computed or stored (a permission verdict, fault output, execution state); the access address, compared with stored state; and the address, write enable and data of a write to a register of this unit. (2) Not covered: the whole record port, a non-record input port (a peer's flow-control line, an interrupt or debug request), and a port or field wired into an instance.
  Outcome: it only refines a decision this unit computes from other information: the processor holds that state; the record carries a copy. Such a field or wire is part of the decision it refines (step 3), not a piece of its own, although steps 1 and 2 would name it and 2.4, 4.2 and 4.4 point at privilege and debug modes: keep no concept for it, nor list it under "Enters Through" or cite its lines as held lines, except a line assigning an element this rule judges as usual.
  Evidence: Judge what a field tells from port field names and their uses; say so.

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
