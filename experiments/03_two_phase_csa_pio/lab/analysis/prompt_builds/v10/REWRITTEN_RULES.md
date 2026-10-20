# Rewritten critical rules (v10 drafts, not assembled into a prompt)

Built 2026-10-15 by the rewrite workflow (writer, skeptic, reviser per group of rules; evidence in dossiers/), then
trimmed in code: "Criteria:" means all criteria must hold, "Criteria (any of):" marks alternatives, and an empty
"Exceptions" slot is left out. Every text passes the project prompt check (check_rule_draft.py, 0 blockers).

Shared procedure (once per phase, in the test context; 56 words):

> - Reading a rule. Check its scope, then each criterion, then each exception, in that order. Its outcome follows only for an element in scope that meets every criterion (one, where marked "any of") and that no exception covers; a criterion that the RTL, or the evidence the rule names, does not show is not met.

## Word counts

| Rule | Title | Job | Phase 1 words v9 → v10 | Phase 2 words v9 → v10 |
|---|---|---|---|---|
| P1-05 | Forwarded transactions | reworded + structure | 438 → 472 | 567 → 611 |
| P1-07 | Bus handshake copies | reworded + structure | 507 → 547 | 380 → 403 |
| P1-23 | Access command fields | reworded + structure | 278 → 313 | 209 → 231 |
| P1-22 | Operation selectors | reworded + structure | 286 → 311 | 282 → 299 |
| P1-27 | Processor context fields | reworded + structure | 252 → 263 | 211 → 223 |
| P1-04 | Pacing pulses | reworded + structure | 125 → 138 | 148 → 141 |
| P1-02 | Clocks and resets | reworded + structure | 362 → 368 | 377 → 397 |
| P1-08 | Working values | reworded + structure | 91 → 114 | 267 → 300 |
| P1-09 | Slices | reworded + structure | 75 → 84 | 85 → 96 |
| P1-14 | Port buffers | reworded + structure | 346 → 395 | 252 → 274 |
| P1-17 | Buffer and engine status bits | reworded + structure | 202 → 219 | 146 → 163 |
| P1-10 | Hand-offs | reworded + structure | 177 → 183 | 174 → 184 |
| P1-16 | Serial shift registers | reworded + structure | 120 → 123 | 210 → 200 |
| P1-15 | Sequencing state | structure only | 489 → 491 | 514 → 516 |
| P1-18 | Port options | structure only | 194 → 207 | 166 → 182 |
| P1-24 | Per-region checks | structure only | 90 → 98 | 0 → 0 |
| P1-06 | Second copies | structure only | 71 → 76 | 70 → 80 |
| | **All 17** | | **4103 → 4402 (+299)** | **4058 → 4300 (+242)** |


---

## P1-05 Forwarded transactions
Why it was rewritten: read two ways in 7 modules (28 signals); Phase 1 / Phase 2 conflict on OR-merged bus responses (decision D2).

**Word changes, Phase 1 wording** (6):

- …it or computes from **[it:]** → **[it and]**
- …it: it only moves **[+]** → **[between unit ports,]**
- …IP, between such instances, **[+]** → **[through a register stage,]**
- …register contents an instance **[+]** → **[other than a buffer or register stage]**
- …written back to a **[register);]** → **[register), unless that statement mixes only relayed data, bus responses and constants;]**
- …and data the unit **[stores,]** → **[stores (not a register stage's copy),]**

**Word changes, Phase 2 wording** (6):

- …it or computes from **[it:]** → **[it and]**
- …it: it only moves **[+]** → **[between unit ports,]**
- …IP, between such instances, **[+]** → **[through a register stage,]**
- …register contents an instance **[+]** → **[other than a buffer or register stage]**
- …written back to a **[register);]** → **[register), unless that statement mixes only relayed data, bus responses and constants;]**
- …and data the unit **[stores,]** → **[stores (not a register stage's copy),]**

**Phase 1 wording, as tested:**

```
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
```

**Phase 2 wording, as tested:**

```
- Forwarded transactions (a).
  Scope: An internal array.
  Criteria: (1) whose elements, one per port, this unit sets each to a whole bus request or response record (2.6); (2) copied from one record or a constant.
  Exceptions: A single strobe, enable or request flag a decision gates.
  Outcome: never qualifies for any conceptual asset: it only passes the transaction on, and a select or compare gating an element's strobe only decides that field (2.2) or mixes into it (2.6), so the decision stays where it is computed. A select computed from that compare (such as a bit-per-port vector) is the decision's own element and stays its primary. If the compare is inline in a condition, the decision has no element of its own and adds no primary, even when the held lines assign the array; do not move the primary to the record the array copies or its fields, which only feed the compare or carry the transaction.
- Forwarded transactions (b).
  Scope: A record.
  Criteria: (1) this unit only wires between a unit port and the port map of an instance of another IP; (2) with no statement of this unit reading or writing it or its fields (a constant tied to it in a generate branch lacking the instance is no such statement).
  Exceptions: a record this unit's statements read or write, a non-record port even if wired straight into an instance, and an element of this unit deciding whether or where the record passes.
  Outcome: never qualifies for any conceptual asset, nor do its fields: the instance holds the value; the record only carries it.
- Forwarded transactions (c).
  Scope: Relayed data is data a transfer carries into or out of the unit (data loaded or stored, instruction words fetched, messages received or sent).
  Criteria: (1) no statement of this unit stores it or computes from it; (2) it only moves between unit ports, between a unit port and an instance of another IP, between such instances, through a register stage, or into a statement only mixing it with other values (an OR, a multiplexer).
  Exceptions: a port of a bus whose address this unit drives on a non-record output port of its own and whose acknowledge it takes on a non-record input port of its own: judge each such port as usual (2.6, 2.7), but under a conceptual asset about what crosses that bus the relayed-data bar still keeps every other element from being primary (each can be a secondary of those ports, 2.7); a transfer's address and direction; a wait or fault flag; an interrupt or debug request; a register read-back word, and the register contents an instance other than a buffer or register stage holds; an arithmetic, logic or compare result an instance computes; the value a mixing statement writes (such as the value written back to a register), unless that statement mixes only relayed data, bus responses and constants; and data the unit stores (not a register stage's copy), shifts through its own register, generates or computes from, even when a buffer instance also holds it.
  Outcome: No element qualifies as primary for a conceptual asset about relayed data, alone or with only the acknowledge and ready lines timing its transfer, even in a unit executing instructions and where 4.2 points at it: Phase 1 does not keep such a concept, so it has no secondary (step 5); under other conceptual assets its elements keep their usual labels.
  Evidence: Judge from port names which instance ports carry relayed data and which a computed result, and say so; judge from port names which ports are that bus's address, acknowledge and other lines, and say so.
```


---

## P1-07 Bus handshake copies
Why it was rewritten: read two ways in 5 modules (9 signals).

**Word changes, Phase 1 wording** (2):

- …not information of their **[own.]** → **[own, except an acknowledge also gating what a read returns.]**
- …software-set lock guarding later **[accesses;]** → **[accesses (not a copied lock bit);]**

**Word changes, Phase 2 wording** (2):

- …software-set lock guarding later **[accesses;]** → **[accesses (not a copied lock bit);]**
- …response; and a cache's **[hit.]** → **[hit, each with its next-value signal.]**

**Phase 1 wording, as tested:**

```
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
```

**Phase 2 wording, as tested:**

```
- Bus handshake copies (b).
  Scope: In a unit passing bus requests from an input bus request port to an output one, a register of one bit, or one bit per requester, not a request waiting for a grant (a rule below).
  Criteria: (1) every assignment to it (directly or through its next-value signal), apart from clearing or holding it, copies or ORs in only the strobe, lock bit or response error bit of the access in progress, or sets it when a test reading only that access's fields and build-time values holds (a route bit); (2) the unit reads it only to start, pass on, route, time or end that access, the access it serves or that locked sequence, or to drop words that access fetched.
  Exceptions: the grant, its select and strobe; an address decode choosing which of several output bus request ports gets the access; a pending fence or flush clearing what the unit stores; a busy flag set when the unit itself issues an access; a timeout count, its error and its suppression flag; a reservation; a software-set lock guarding later accesses (not a copied lock bit); a read enable deciding whether stored data leaves on the response; and a cache's hit, each with its next-value signal.
  Outcome: holds no information of its own: the register only re-times a value the access already carries. Such a register and a signal used only to compute its next value never qualify for any conceptual asset: one about such registers alone has no primary, and barring them makes no other element primary instead. They can be secondaries only in direction b (2.7).
- Bus handshake copies (c).
  Scope: A one-bit register.
  Criteria: (1) that one unconditional statement sets on every clock edge to a stored state bit or flag of this unit, copied or inverted and ANDed only with terms saying when it applies (a request strobe, its read or write bit, an operation-type decode); (2) that only a bus response's acknowledge or data fields read.
  Exceptions: that state, where held; a register set only from the unit's input ports (a read enable from a strobe and a read or write bit); and a flag that a condition sets to a constant (a timeout error raised at a count's limit).
  Outcome: only re-times that state to the response. It is never primary for any conceptual asset but can be a secondary (2.7).
```


---

## P1-23 Access command fields
Why it was rewritten: read two ways in 10 modules (12 signals).

**Word changes, Phase 1 wording** (5):

- …- Access command fields. **[On]** → **[For accesses on]**
- …together carrying an access) **[carrying accesses]** → **[removed]**
- …only lets a register **[+]** → **[or FIFO]**
- …to a unit output **[port;]** → **[port other than as an acknowledge;]**
- …port; an operation's start **[pulse.]** → **[pulse (not an access's strobe or write enable).]**

**Word changes, Phase 2 wording** (5):

- … **[On]** → **[For accesses on]**
- …together carrying an access) **[carrying accesses]** → **[removed]**
- …only lets a register **[+]** → **[or FIFO]**
- …to a unit output **[port,]** → **[port other than as an acknowledge,]**
- …and an operation's start **[pulse.]** → **[pulse (not an access's strobe or write enable).]**

**Phase 1 wording, as tested:**

```
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
```

**Phase 2 wording, as tested:**

```
- Scope: Accesses on a record port (never on non-record ports, even ones together carrying an access) addressing this unit's own registers, FIFOs, locks or memory words (not a cache's copies).
  Criteria (any of): (1) the fields only saying whether an access happens, its direction and which register, FIFO or bytes it reaches (a strobe, a read or write bit, register-select address bits, byte enables; an address indexing a memory's stored words is the access address, not one of them); (2) a write enable whose assignment reads only these fields and that only lets a register or FIFO take the written data.
  Exceptions: Judged as usual: a separate signal decoded from these fields that gates or masks what a read returns or pops a FIFO of data the unit generates itself (the decision's own element), a register loaded with such a field's value, a request held until served, a select routing it on, a strobe driven on to a unit output port other than as an acknowledge, and an operation's start pulse (not an access's strobe or write enable).
  Outcome: they are part of the information the access writes or reads, not information of their own. They never qualify for any conceptual asset, whether or not the port is a bus request or response record, and can be secondaries (2.7, direction b) of the element the access writes, reads or decides.
```


---

## P1-22 Operation selectors
Why it was rewritten: read two ways in 6 modules (12 signals); start from v9 (decision D4).

**Word changes, Phase 1 wording** (4):

- …a start command or **[pulse,]** → **[pulse saying when the operation starts,]**
- …plain bus read or **[write is not covered: on a record port, Access command fields judges]** → **[write,]**
- …read enable made from **[it.]** → **[it are not covered.]**
- …port or a request-record **[field)]** → **[field, not of a bus request (2.6))]**

**Word changes, Phase 2 wording** (3):

- …a start command or **[pulse,]** → **[pulse saying when the operation starts,]**
- …plain bus read or **[write; on a record port, the bar above on access command fields judges]** → **[write,]**
- …port or a request-record **[field)]** → **[field, not of a bus request (2.6))]**

**Phase 1 wording, as tested:**

```
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
```

**Phase 2 wording, as tested:**

```
- Scope: In a unit executing an instruction or atomic memory operation a processor issues to it (a coprocessor, an atomic read-modify-write).
  Criteria (any of): (1) instruction or request fields only picking the operation or its result form (an opcode, a function code, an instruction-type bit); (2) their stored copies; (3) flags decoded from them only naming the operation. A flag whose assignment reads more than these fields (a start or valid signal, a state) does not only name the operation.
  Exceptions: (1) Judged as usual: a start command or pulse saying when the operation starts, even one decoded per operation (a multiply start, a divide start), a register access's address and write enable, a completion flag, and a setting decoded from these fields (not a copy) changing how operands are read (such as signedness). (2) Not covered: a plain bus read or write, its read or write bit and a read enable made from it.
  Outcome: they never qualify for any conceptual asset, being part of the operation they pick, not decisions of their own; they can be secondaries only in direction b (2.7).
- Scope: In a unit executing an instruction or atomic memory operation a processor issues to it, a register.
  Criteria: (1) whose value, apart from constants and itself, comes only from one source operand input (a port or a request-record field, not of a bus request (2.6)) when the operation starts, directly or through its next-value wire; (2) reaches an output port only through the element holding the result.
  Outcome: it only holds that operand while the operation uses it (2.6: a copy kept only while the value moves). It and its next-value wire never qualify as primary for any conceptual asset: the operand input keeps its own label; they can be secondaries (2.7).
```


---

## P1-27 Processor context fields
Why it was rewritten: read two ways in 2 modules (7 signals).

**Word changes, Phase 1 wording** (1):

- …information when this unit **[+]** → **[reads it and]**

**Word changes, Phase 2 wording** (1):

- …information when this unit **[+]** → **[reads it and]**

**Phase 1 wording, as tested:**

```
- Processor context fields.
  Scope: A field, of a record input port other than a bus request or response record port (2.6).
  Criteria: (1) tells the processor's privilege mode, whether it is in debug mode or takes a trap, or whether the current access is a fetch or data access, read or write; (2) this unit reads it and only tests it (a condition, select, compare with a fixed value, gate on another result), directly or through a wire only selecting between such fields.
  Exceptions: (1) Judged as usual: the decision such a field refines, where computed or stored (a permission verdict, fault output, execution state); the access address, compared with stored state; and the address, write enable and data of a write to a register of this unit. (2) Not covered: the whole record port, a non-record input port (a peer's flow-control line, an interrupt or debug request), and a port or field wired into an instance.
  Outcome: it only refines a decision this unit computes from other information: the processor holds that state; the record carries a copy. Such a field or wire is part of the decision it refines (step 3), not a piece of its own, although steps 1 and 2 would name it and 2.4, 4.2 and 4.4 point at privilege and debug modes: keep no concept for it, nor list it under "Enters Through" or cite its lines as held lines, except a line assigning an element this rule judges as usual.
  Evidence: Judge what a field tells from port field names and their uses; say so.
```

**Phase 2 wording, as tested:**

```
- Scope: A field, of a record input port other than a bus request or response record port (2.6).
  Criteria: (1) tells the processor's privilege mode, whether it is in debug mode or takes a trap, or whether the current access is a fetch or data access, read or write; (2) this unit reads it and only tests it (a condition, select, compare with a fixed value, gate on another result), directly or through a wire only selecting between such fields.
  Exceptions: (1) Judged as usual: the decision such a field refines, where computed or stored (a permission verdict, fault output, execution state); the access address, compared with stored state; and the address, write enable and data of a write to a register of this unit. (2) Not covered: the whole record port, a non-record input port (a peer's flow-control line, an interrupt or debug request), and a port or field wired into an instance.
  Outcome: it only refines a decision this unit computes from other information: the processor holds that state; the record carries a copy. Such fields and wires never qualify for any conceptual asset; where 2.6 would make only these primary, the conceptual asset has none. They can be secondaries only in direction b (2.7).
  Evidence: Judge what a field tells from port field names and their uses; say so.
```


---

## P1-04 Pacing pulses
Why it was rewritten: read two ways in 3 modules (7 signals); its Phase 1 bar takes an enable input another rule was written to keep (decision D8).

**Word changes, Phase 1 wording** (7):

- …setting (step 3), unless **[+]** → **[it is a pulse]**
- …an output port carries **[the pulse itself (2.2); an output]** → **[(2.2), not a]**
- …pulses only decide or **[time does not count.]** → **[time.]**
- …lines. Not pacing pulses: **[+]** → **[an enable deciding whether the count runs at all,]**
- …until served, a start **[pulse]** → **[pulse, or its copy,]**
- …decoded from a received **[command,]** → **[command or access, a count whose compare with a limit raises a reset, error or interrupt, or sets an output level,]**
- …(sequencing state, below, judges **[a step counter; in a coprocessor, such a count of its busy state is one piece with that state).]** → **[it).]**

**Word changes, Phase 2 wording** (9):

- …any conceptual asset unless **[+]** → **[it is a pulse]**
- …an output port carries **[the pulse itself (2.2);]** → **[(2.2), not]**
- …pulses only decide or **[time does not count.]** → **[time.]**
- …storing the rate setting, **[+]** → **[an enable deciding whether the count runs at all,]**
- …until served, a start **[pulse]** → **[pulse, or its copy,]**
- …decoded from a received **[command, a step counter (sequencing state, below, judges it; in a coprocessor, such a count of its busy state is one piece with that state), and]** → **[command or access,]**
- …limit raises a reset, **[an]** → **[removed]**
- …reset, an error or **[an]** → **[removed]**
- …or sets an output **[level (a timeout or timer count).]** → **[level, and a step counter (sequencing state, below, judges it).]**

**Phase 1 wording, as tested:**

```
- Pacing pulses.
  Scope: A tick, edge pulse or divider count made inside the unit, or an input port used only as a condition letting a tick or count meeting (1) advance.
  Criteria: (1) only to pace another step.
  Exceptions: if it is a pulse an output port carries (2.2) (not a port the pulses only decide or time); an enable deciding whether the count runs at all; a request held until served; a start pulse, or its copy, decoded from a received command or access; a count whose compare with a limit raises a reset, error or interrupt, or sets an output level; a step counter (sequencing state, below, judges it).
  Outcome: part of that step or its rate setting (step 3). Do not name it in any concept's information or cite its lines as held lines.
```

**Phase 2 wording, as tested:**

```
- Pacing pulses.
  Scope: A tick, edge pulse or divider count made or picked inside the unit.
  Criteria: (1) only to pace a step (apart from restarting itself, it only makes such a pulse or lets the step advance).
  Exceptions: if it is a pulse an output port carries (2.2) (not a port the pulses only decide or time); the element storing the rate setting; an enable deciding whether the count runs at all; a request held until served; a start pulse, or its copy, decoded from a received command or access; a count whose compare with a limit raises a reset, error or interrupt, or sets an output level; a step counter (sequencing state, below, judges it).
  Outcome: not primary for any conceptual asset. It can be a secondary only of a primary whose update it gates (2.7, direction b).
```


---

## P1-02 Clocks and resets
Why it was rewritten: unclear wording in 3 of 10 sampled one-sided cases (and 7 over-applied).

**Word changes, Phase 1 wording** (3):

- …resets. Clock and reset **[inputs,]** → **[inputs (1(b)),]**
- …while the peer stretches **[it), although this rule judges other clock settings as usual.]** → **[it).]**
- …settings stays, without it. **[Clock-controlling]** → **[Other clock-controlling]**

**Word changes, Phase 2 wording** (6):

- …qualifies for any conceptual **[asset:]** → **[asset, nor does that line itself:]**
- …often the line toggles), **[an enable,]** → **[other clock-controlling settings (an enable),]**
- …be a secondary (2.7). **[A]** → **[Clock and reset inputs (1(b)), and a]**
- …chain or reset output **[port]** → **[port,]**
- …reset output port never **[qualifies]** → **[qualify]**
- …reset (a reset shift **[register): they only carry a decision judged where it is computed.]** → **[register).]**

**Phase 1 wording, as tested:**

```
- Clocks and resets (a).
  Scope: any unit.
  Criteria (any of): (1) clock and reset inputs (1(b)); (2) a reset request the unit only combines, gates, registers or passes to a reset chain or reset output port (its copies and that output port included); (3) chains only synchronizing or releasing a reset (a reset shift register, a registered reset copy).
  Exceptions: a reset-triggering decision (a timeout) where it is computed, not a copy the unit only gates or registers, except as (c) says; the cause record; a compare outcome restarting a counter.
  Outcome: not conceptual assets under any question.
  Evidence: Do not cite their lines as held lines.
- Clocks and resets (b).
  Scope: any unit.
  Criteria (any of): (1) a serial link's clock line the unit drives to, or senses from, a peer device; (2) a setting or decision whose only use, apart from a read-back, is to shape that line (polarity, phase against the data, holding it while the peer stretches it); a setting's only use is to shape a serial link's clock line also when, apart from its read-back, its counterparts show it gives value to or decides only the element driving that line, and that element gives value to or decides nothing but the line, even where the line's phase sets when the peer samples or sends data.
  Exceptions: the link's data and select lines, its rate setting and the unit's clock-enable outputs; other clock-controlling settings or requests (an enable, a rate).
  Outcome: not a conceptual asset: keep no concept for it and do not cite its lines as held lines; a transfer-mode, format or rate concept holding other settings stays, without it.
- Clocks and resets (c).
  Scope: A decision that a write was refused or carried a wrong value (a write while locked, a wrong password), its gated or registered copies, and a setting choosing only whether such a violation resets.
  Criteria: (1) apart from a read-back, they only request a reset and record its cause.
  Exceptions: the cause record, the lock refusing the write, and a compare outcome restarting a counter.
  Outcome: not conceptual assets, although step 3 makes a compare of a written value with a fixed value a piece.
```

**Phase 2 wording, as tested:**

```
- Clocks and resets (a).
  Scope: any unit.
  Criteria (any of): (1) clock and reset inputs (1(b)); (2) a reset request that this unit only combines, gates, registers or passes on to a reset chain or reset output port, the input port bringing it in, its copies, or that output port; (3) a chain only synchronizing or releasing a reset (a reset shift register).
  Exceptions: the record of a reset's cause, a compare outcome that restarts a counter, and, except as (c) says, a decision triggering a reset (such as a timeout), where it is computed, not a copy of it that the unit only gates or registers.
  Outcome: never qualify for any conceptual asset.
- Clocks and resets (b).
  Scope: any unit.
  Criteria (any of): (1) a setting or decision whose only use, apart from a read-back, is to shape a serial link's clock line that the unit drives to or senses from a peer device (its polarity, its phase against the data, or holding it while the peer stretches it); a setting's only use is to shape a serial link's clock line also when, apart from its read-back, its counterparts show it gives value to or decides only the element driving that line, and that element gives value to or decides nothing but the line, even where the line's phase sets when the peer samples or sends data; (2) that line itself.
  Exceptions: the link's data and select lines, its rate setting (how often the line toggles), other clock-controlling settings (an enable), and the unit's clock-enable outputs.
  Outcome: never qualifies for any conceptual asset, even a transfer-mode, format or rate concept: Phase 1 does not keep it as one; it can be a secondary (2.7).
- Clocks and resets (c).
  Scope: A decision that a write was refused or carried a wrong value (a write while locked, a wrong password), its gated or registered copies, and a setting choosing only whether such a violation resets.
  Criteria: (1) their only uses, apart from a read-back, are to request a reset and record its cause.
  Exceptions: the cause record, the lock refusing the write, a compare outcome that restarts a counter, a decision triggering a reset for another cause (such as a timeout) where it is computed, and a refused access raising a trap, a fault or a bus error.
  Outcome: never qualify for any conceptual asset.
```


---

## P1-08 Working values
Why it was rewritten: read two ways in 6 modules (7 signals); Phase 2 has an exception Phase 1 lacks (decision D3).

**Word changes, Phase 1 wording** (6):

- …or round value, a **[synchronizer stage,]** → **[debiasing step with its state and flag, although step 2 would call them]**
- …a synchronizer stage, a **[debiasing step)]** → **[decision)]**
- …concepts of their own. **[So are]** → **[Judged as usual:]**
- …own. So are the **[state and flag made inside]** → **[finished result, even an instance output, held where computed or an output port takes it from;]**
- …flag made inside a **[debiasing step to choose which raw bits it accepts: although step 2 would call them a decision, they only shape that result, like a compare picking a minimum (step 3).]** → **[count.]**
- …name a synchronizer stage **[+]** → **[(a register only shifting in one unit input port's bit, apart from constants)]**

**Word changes, Phase 2 wording** (8):

- …maximum), and a debiasing **[step's]** → **[step with its]**
- …debiasing step's state and **[flag choosing which raw bits it accepts.]** → **[flag.]**
- …unit port; a signal **[handed]** → **[taking an instance output whole or handing the finished result]**
- …signal handed whole to **[or from]** → **[removed]**
- …a count; a setting **[(such as signedness);]** → **[that changes how operands are read (signedness);]**
- …serial port's data shift **[register;]** → **[register and a one-bit register feeding it;]**
- …software reads back); a **[register whose new bit comes from a stage (a]** → **[removed]**
- …register assembling a received **[word);]** → **[word from a stage's bits;]**

**Phase 1 wording, as tested:**

```
- Working values (a).
  Scope: inside a computation.
  Criteria (any of): (1) a partial sum, product or round value; (2) a debiasing step with its state and flag, although step 2 would call them a decision.
  Exceptions: judged as usual: the finished result, even an instance output, held where computed or an output port takes it from; a count.
  Outcome: partial results are part of the result they produce (step 3), not concepts of their own.
- Working values (b).
  Scope: a synchronizer stage.
  Criteria: a register only shifting in one unit input port's bit, apart from constants.
  Outcome: do not name it in any concept's information or cite its lines as held lines.
```

**Phase 2 wording, as tested:**

```
- Working values (a).
  Scope: a computation of this unit.
  Criteria (any of): (1) a partial sum or product, an addend, a subtraction step or round value; (2) a value before the final sign step; (3) a value computed only to be copied, whole or in part, into the finished result's register; (4) a compare only picking that result (a minimum or maximum); (5) a debiasing step with its state and flag.
  Exceptions: judged as usual: the element holding the finished result or that an output port takes it from, even while holding operand copies or partial values; a unit port; a signal taking an instance output whole or handing the finished result whole to an instance; a count; a setting that changes how operands are read (signedness); a serial port's data shift register and a one-bit register feeding it; and any other decision (such as a compare whose result picks or triggers what happens next, or checks combined per region or entry).
  Outcome: partial results belong to the computation's result and never qualify for any conceptual asset.
- Working values (b).
  Scope: a synchronizer stage; a wire only copying one of its bits is part of it.
  Criteria: a register whose assignments, apart from constants, only (1) copy in one unit input port's bit (directly or through a wire or type conversion only copying it) and (2) shift its own earlier bits along.
  Exceptions: judged as usual: the port itself; a register copying a port with none of its own earlier bits (an input register software reads back); a shift register assembling a received word from a stage's bits; and an element mixing the port or a stage's bits with other values (a request held until served, a sticky flag).
  Outcome: it is not primary for any conceptual asset.
```


---

## P1-09 Slices
Why it was rewritten: unclear wording in 7 of 10 sampled one-sided cases.

**Word changes, Phase 1 wording** (5):

- …(not a port) whose **[only assignment copies part of]** → **[every value, apart from reset and another generate branch's constants, is]**
- …part of one element's **[bits (a slice),]** → **[slices]**
- …bits (a slice), or **[joins signals each doing so from the same element,]** → **[indexed bits, alone or joined, even through signals,]**
- …request or response record **[port or]** → **[port,]**
- …or a field of **[one:]** → **[one, or a write's data:]**

**Word changes, Phase 2 wording** (5):

- …(not a port) whose **[only assignment copies part of]** → **[every value, apart from reset and another generate branch's constants, is]**
- …part of one element's **[bits (a slice),]** → **[slices]**
- …bits (a slice), or **[joins signals each doing so from the same element,]** → **[indexed bits, alone or joined, even through signals,]**
- …request or response record **[port or]** → **[port,]**
- …or a field of **[one:]** → **[one, or a write's data:]**

**Phase 1 wording, as tested:**

```
- Slices.
  Scope: a signal (not a port).
  Criteria: whose every value, apart from reset and another generate branch's constants, is one element's slices or indexed bits, alone or joined, even through signals.
  Exceptions: that element is a bus request or response record port, a field of one, or a write's data: such a slice is judged as usual (2.6).
  Outcome: it only carries that element's value (2.2) and is not a piece of its own: do not cite its lines as held lines.
```

**Phase 2 wording, as tested:**

```
- Slices.
  Scope: a signal (not a port).
  Criteria: whose every value, apart from reset and another generate branch's constants, is one element's slices or indexed bits, alone or joined, even through signals.
  Exceptions: that element is a bus request or response record port, a field of one, or a write's data: such a slice is judged as usual (2.6).
  Outcome: it only carries that element's value (2.2) and never qualifies as primary for any conceptual asset: the element it takes from keeps its own label, and the signal can be a secondary (2.7, direction a).
```


---

## P1-14 Port buffers
Why it was rewritten: Phase 1 wording unclear in 4 of 5 sampled one-sided cases; 18 contradictions are the same clause filed both ways.

**Word changes, Phase 1 wording** (15):

- …flags (holds data, has **[room),]** → **[room, half full),]**
- …pop strobes, a command **[+]** → **[used]**
- …strobes, a command only **[clearing]** → **[to clear]**
- …clearing it, and a **[+]** → **[push-while-full]**
- …it, and a flag **[recording a push while full]** → **[removed]**
- …would call some a **[decision.]** → **[decision; cite no line assigning or wiring them as a held line.]**
- …and a unit enable **[that]** → **[removed]**
- …unit enable that also **[clears]** → **[clearing]**
- …data the unit generates **[itself]** → **[rather than receives]**
- …value moves), so the **[signal]** → **[signals (not ports)]**
- …its write-data input and **[the signal]** → **[driven by]**
- …signal its read-data output **[drives]** → **[removed]**
- …drives only carry the **[word;]** → **[word and are not pieces of their own;]**
- …it crosses the unit's **[boundary. Keep the buffered data as]** → **[boundary at]**
- …buffered data as a **[piece, but cite]** → **[port. Cite]**

**Word changes, Phase 2 wording** (12):

- …its fill flags (holds **[data or]** → **[data,]**
- …(holds data or has **[room),]** → **[room, half full),]**
- …pop strobes, a command **[+]** → **[used]**
- …strobes, a command only **[clearing]** → **[to clear]**
- …request, a ready-to-receive line), **[+]** → **[and]**
- …enable also clearing the **[FIFO, and the flags and controls of]** → **[FIFO;]**
- …data the unit generates **[+]** → **[rather than receives]**
- …the unit generates (random **[bits).]** → **[bits) is not covered.]**
- …value moves), so the **[signal]** → **[signals (not ports)]**
- …its write-data input and **[the signal]** → **[driven by]**
- …signal its read-data output **[drives]** → **[removed]**
- …it crosses the unit's **[boundary.]** → **[boundary at a port.]**

**Phase 1 wording, as tested:**

```
- Port buffers (a).
  Scope: a FIFO instance's fill flags (holds data, has room, half full), push and pop strobes, a command used only to clear it, and a push-while-full flag (even a register of this unit).
  Criteria: the FIFO's write data is a unit input port's value (a bus write, or bits shifted in from a serial input port).
  Exceptions: judged as usual: the buffered data, an output port these flags decide (an interrupt request, a ready-to-receive line), and a unit enable also clearing the FIFO; a FIFO holding data the unit generates rather than receives (random bits) is not covered.
  Outcome: not pieces of their own, although step 2 would call some a decision: the FIFO only buffers data between two ports; they only time, gate, clear or report on that data.
  Evidence: cite no line assigning or wiring them as a held line; judge from port names that an instance is a FIFO, which outputs are its flags and which ports carry its data, and say so.
- Port buffers (b).
  Scope: that FIFO (random bits).
  Criteria (any of): (1) its holds-data flag that a statement of this unit tests to return either that data or something else (the flag withholds the data); (2) a register whose only use is to clear that FIFO (it discards the data).
  Exceptions: judged as usual: its other flags and its push, pop and enable controls.
  Outcome: each their own piece (step 2) that no step-3 clause folds into that data. If the flag, then held at the line wiring it out of the FIFO, with the read-data line returning the flag as its exit (step 6). If the register, then held at the line assigning it.
- Port buffers (c).
  Scope: any FIFO instance, whatever data it holds; signals (not ports).
  Criteria (any of): (1) wired to its write-data input; (2) driven by its read-data output.
  Outcome: the FIFO keeps each word only while the word moves (2.6: a copy kept only while the value moves); they only carry the word and are not pieces of their own; the buffered data is judged where the unit generates it (random bits) or where it crosses the unit's boundary at a port.
  Evidence: cite no line assigning or wiring those two signals as a held line; leave "Held Lines" empty if no other line holds the data.
```

**Phase 2 wording, as tested:**

```
- Scope: a FIFO instance's fill flags (holds data, has room, half full), push and pop strobes, a command used only to clear it, and a push-while-full flag (even a register of this unit).
  Criteria: the FIFO's write data is a unit input port's value (a bus write, or bits shifted in from a serial input port).
  Exceptions: judged as usual: the buffered data, an output port these flags decide (an interrupt request, a ready-to-receive line), and a unit enable also clearing the FIFO; a FIFO holding data the unit generates rather than receives (random bits) is not covered.
  Outcome: the FIFO only buffers data between two ports: they only time, gate, clear or report on that data and never qualify for any conceptual asset; barring them makes no other element primary instead.
  Evidence: judge from port names that an instance is a FIFO, which outputs are its flags and which ports carry its data, and say so.
- Scope: any FIFO instance, whatever data it holds; signals (not ports).
  Criteria (any of): (1) wired to its write-data input; (2) driven by its read-data output.
  Outcome: the FIFO keeps each word only while the word moves (2.6: a copy kept only while the value moves); these two signals only carry the word, never qualify as primary for any conceptual asset, even where 2.6's inward or outward clause, or this step's list sparing a signal handed whole to or from an instance, would make them primary; they can be secondaries (2.7, direction a). The buffered data is judged where the unit generates it (random bits) or where it crosses the unit's boundary at a port.
```


---

## P1-17 Buffer and engine status bits
Why it was rewritten: read two ways in 4 modules (6 signals).

**Word changes, Phase 1 wording** (3):

- …data the unit generates **[itself)]** → **[rather than receives)]**
- …itself) or on sequencing **[state:]** → **[state (state register, counter, or busy or done flag derived from them):]**
- …the same read word **[(a]** → **[(the buffered data, a]**

**Word changes, Phase 2 wording** (5):

- …data the unit generates **[itself)]** → **[rather than receives)]**
- …itself) or on sequencing **[state:]** → **[state (state register, counter, or busy or done flag derived from them):]**
- …the same read word **[(a]** → **[(the buffered data, a]**
- …setting, selection or lock, **[the record of]** → **[removed]**
- …record of a reset's **[cause),]** → **[cause record),]**

**Phase 1 wording, as tested:**

```
- Buffer and engine status bits.
  Scope: a status bit a bus read returns.
  Criteria: every element it copies (even inverted) or combines is barred by this call's rule on a FIFO only buffering data between two ports (never a flag of a FIFO holding data the unit generates rather than receives) or on sequencing state (state register, counter, or busy or done flag derived from them).
  Exceptions: not covered: (1) a bit returning anything else, even in the same read word (the buffered data, a stored setting, selection or lock, a reset's cause record); it belongs to the piece it returns, as that piece's exit (step 6); (2) the output ports these elements decide (an interrupt request, a ready-to-receive line), a register a test or debug access port shifts out, and, in a unit executing instructions, the word an instance outputs for reads of its control and status registers.
  Outcome: not information of its own: it only tells software whether the buffered or shifted data can move or was lost, which that data, its settings and the output ports these elements decide already cover. Although step 1 names status and 4.3 status signals, keep no concept for such bits, alone or grouped as the status software reads, and cite no read-data line returning them as a held line.
```

**Phase 2 wording, as tested:**

```
- Scope: a status bit a bus read returns.
  Criteria: every element it copies (even inverted) or combines is barred by this call's rule on a FIFO only buffering data between two ports (never a flag of a FIFO holding data the unit generates rather than receives) or on sequencing state (state register, counter, or busy or done flag derived from them).
  Exceptions: a bit returning anything else, even in the same read word (the buffered data, a stored setting, selection or lock, a reset's cause record), is not covered.
  Outcome: not information of its own: it only tells software whether the buffered or shifted data can move or was lost, which that data, its settings and the output ports these elements decide already cover. The elements such a bit copies or combines stay barred under a conceptual asset about that status; where only they would be primary, it has none. They can be secondaries only as the rule barring them allows (2.7).
```


---

## P1-10 Hand-offs
Why it was rewritten: read two ways in 5 modules (18 signals).

**Word changes, Phase 1 wording** (1):

- …record an instance outputs **[+]** → **[on a record port]**

**Word changes, Phase 2 wording** (1):

- …record an instance outputs **[+]** → **[on a record port]**

**Phase 1 wording, as tested:**

```
- Hand-offs.
  Scope: check each port-map line where an instance's non-record output port drives a signal another instance or this unit's logic reads; a wait, fault or write-enable flag, or an access address.
  Criteria: that one instance outputs on a non-record port to another instance or this unit's logic.
  Exceptions: a field of a record an instance outputs on a record port is never a hand-off, even wired alone into another instance's non-record port; if Port buffers covers it, then this rule does not apply.
  Outcome: a hand-off: its own piece (step 2). No step-3 clause or other rule folds it, even when it travels with the data it qualifies, when another instance outputs the same address earlier or later (cite each output's port-map line, in one piece), or when it is one bit of a count: then hold it at the line assigning that bit to the instance output, and a count kept only to make it belongs to this piece.
  Evidence: if the RTL cannot show which kind it is, judge from the port names at either end and say so.
```

**Phase 2 wording, as tested:**

```
- Scope: a wait, fault or write-enable flag, or an access address.
  Criteria: that one instance outputs on a non-record port to another instance or this unit's logic.
  Exceptions: a field of a record an instance outputs on a record port is never a hand-off, even wired alone into another instance's non-record port; apart from the port-buffer bar on a FIFO, no bar in this step covers a hand-off.
  Outcome: a hand-off: label a hand-off primary for its conceptual asset where the instance outputs it: the output port of an instance of this file when this unit only wires that port into another instance, and otherwise the unit signal the port map drives; when another instance outputs the same address earlier or later, label each output. When a hand-off is one bit of a count, the line assigning that bit to the output is where it is computed: the count is not primary for that conceptual asset, and can be its secondary (2.7).
  Evidence: if the RTL cannot show which kind it is, judge from the port names at either end and say so.
```


---

## P1-16 Serial shift registers
Why it was rewritten: Phase 2 wording unclear in 4 of 5 sampled one-sided cases.

**Word changes, Phase 1 wording** (0):

- none

**Word changes, Phase 2 wording** (2):

- … **[A non-record unit port that moves the conceptual asset's value one bit per step crosses the boundary whole, as every bit passes it: the RTL shifts the port's bit into one end of a register carrying that value (2.2), or drives the port from such a register's end bit, even through forwarding wires, synchronizer stages or one-bit registers, and even if the register holds other fields or the port carries other bits at other steps. Label the port primary, not secondary as a path to the register, which keeps its own label. A serial clock line carries no bit of the value, so it is never such a port.]** → **[removed]**
- …secondary (2.7, direction a). **[+]** → **[A non-record unit port (not a serial clock line) that moves the conceptual asset's value one bit per step crosses the boundary whole, as every bit passes it: the RTL shifts the port's bit into one end of a register carrying that value (2.2), or drives the port from such a register's end bit, even through forwarding wires, synchronizer stages or one-bit registers, and even if the register holds other fields or the port carries other bits at other steps. Label the port primary, not secondary as a path to the register, which keeps its own label.]**

**Phase 1 wording, as tested:**

```
- Serial shift registers.
  Scope: the data shift register in a unit shifting data bit by bit onto or off a serial data port, paced by the unit's own rate setting.
  Criteria: only holds each word while moving it between that port and the element taking or giving the whole word.
  Outcome: the port is where that data crosses the unit's boundary whole (2.6). Keep the data as a piece: list that port under "Enters Through" or "Leaves Through".
  Evidence: cite the lines reading or driving the port as entry or exit lines, even when they name the shift register; cite no line assigning the shift register as a held line, and leave "Held Lines" empty if no other line holds the data.
```

**Phase 2 wording, as tested:**

```
Scope: the data shift register in a unit shifting data bit by bit onto or off a serial data port, paced by the unit's own rate setting.
Criteria: only holds each word while moving it between that port and the element taking or giving the whole word.
Outcome: the port is where that data crosses the unit's boundary whole (2.6). That shift register never qualifies as primary for any conceptual asset, even though the serial-port sentence above leaves it its own label and the sentences on partial results and synchronizer stages judge it as usual; it can be a secondary (2.7, direction a).
A non-record unit port (not a serial clock line) that moves the conceptual asset's value one bit per step crosses the boundary whole, as every bit passes it: the RTL shifts the port's bit into one end of a register carrying that value (2.2), or drives the port from such a register's end bit, even through forwarding wires, synchronizer stages or one-bit registers, and even if the register holds other fields or the port carries other bits at other steps.
Label the port primary, not secondary as a path to the register, which keeps its own label.
```


---

## P1-15 Sequencing state
Why it was rewritten: over-applied in 10 of 10 sampled one-sided cases: structure only.

**Phase 1 wording, as tested:**

```
- Sequencing state.
  Scope: a state machine's state register or a bit, phase, word or step counter, outside: a coprocessor; a unit shifting in bits it generates; a test or debug access port that a peer's clock paces.
  Criteria: (1) restarts with each transfer or operation the unit performs (even if one bit copies an enable or a queued command picks the first step); (2) is read only to pick that transfer's next step, to time or gate its strobes, commands, shifts, loads, acknowledges and multiplexers, or to point its address at the next word.
  Exceptions: a flag a request or command sets, held until that request is answered; a reservation one access sets and a later one checks; the current grant, a state naming which requester holds a shared path, with the select and strobe it drives; a count whose compare with a limit raises a reset, error or interrupt, or sets an output level, such as a timeout or timer count; that compare's flag or a timeout's suppression flag. Judged as usual: any unit port (even an interrupt request its flags decide), the enable and rate settings, other elements its steps load or drive (a chip-select register, an address), an instance output port assigned one of its bits (a hand-off when another instance reads it), and a peer's command (below).
  Outcome: sequencing state: it only orders steps of information other elements hold, so neither it, an internal busy flag decoded from it, nor an internal done flag it sets at its last step is information of its own. Sequencing state and its internal busy and done flags are not pieces of their own, although step 2 names a state machine's state, a count and a select, and 2.4 control flow (a program's): keep no concept for them.
  Evidence: cite none of their lines as held lines, except one also assigning an element this rule does not bar.
  - Scope: a non-record unit input port.
    Criteria: (1) reaches the unit's logic only through synchronizer stages (registers only shifting that port's bit along, and wires only copying one of their bits) that give value to nothing but each other and decide nothing but a state machine's state register; (2) no conceptual asset holds that state.
    Exceptions: a clock, a reset or a serial link's clock line.
    Outcome: the port's bit is that peer's command to the state machine, information of its own that enters through that port, whose primary is that port (2.6: the input port setting it), never that state register, which the bit only decides (2.2), nor those stages.
  - Scope: in a coprocessor, a count.
    Criteria: (1) that a multi-cycle operation steps every clock cycle of its busy state; (2) whose end test only leaves that state.
    Outcome: a step counter, one piece of information with that state. Keep that state as a concept and hold the count in it, not in the operation's result or its pacing.
```

**Phase 2 wording, as tested:**

```
Scope: a state machine's state register or a bit, phase, word or step counter, outside: a coprocessor; a unit shifting in bits it generates; a test or debug access port that a peer's clock paces.
Criteria: (1) restarts with each transfer or operation the unit performs (even if one bit copies an enable or a queued command picks the first step); (2) is read only to pick that transfer's next step, to time or gate its strobes, commands, shifts, loads, acknowledges and multiplexers, or to point its address at the next word.
Exceptions: a flag a request or command sets, held until that request is answered; a reservation one access sets and a later one checks; the current grant, a state naming which requester holds a shared path, with the select and strobe it drives; a count whose compare with a limit raises a reset, error or interrupt, or sets an output level, such as a timeout or timer count; that compare's flag or a timeout's suppression flag. Judged as usual: any unit port (even an interrupt request its flags decide), the enable and rate settings, other elements its steps load or drive (a chip-select register, an address), an instance output port assigned one of its bits (a hand-off when another instance reads it), and a peer's command (below).
Outcome: sequencing state: it only orders steps of information other elements hold, so neither it, an internal busy flag decoded from it, nor an internal done flag it sets at its last step is information of its own. Sequencing state and its internal busy and done flags never qualify for any conceptual asset, even one about that state or a transfer's control flow; where 2.6 would make only these primary, the conceptual asset has none. They can be secondaries only in direction b (2.7).
  - Scope: a non-record unit input port.
    Criteria: (1) reaches the unit's logic only through synchronizer stages (registers only shifting that port's bit along, and wires only copying one of their bits) that give value to nothing but each other and decide nothing but a state machine's state register; (2) no conceptual asset holds that state.
    Exceptions: a clock, a reset or a serial link's clock line.
    Outcome: the port's bit is that peer's command to the state machine, information of its own that enters through that port, whose primary is that port (2.6: the input port setting it), never that state register, which the bit only decides (2.2), nor those stages.
  - Scope: in a coprocessor, a count.
    Criteria: (1) that a multi-cycle operation steps every clock cycle of its busy state; (2) whose end test only leaves that state.
    Outcome: a step counter, one piece of information with that state. Label the count primary for that state's conceptual asset, not secondary as a transition input.
Outside a coprocessor, sequencing state (below) is not such a decision or setting.
Label a port that step 3 names as setting a state machine's state primary for the conceptual asset about that state; the state register keeps its own label, and synchronizer stages stay barred.
```


---

## P1-18 Port options
Why it was rewritten: over-applied in 9 of 10 sampled one-sided cases: structure only.

**Phase 1 wording, as tested:**

```
- Port options.
  Scope: a setting a bus write stores.
  Criteria (all of), apart from its read-back: (1) its counterparts show it gives value to or decides some element; (2) each is any of: an interrupt request output (it picks which events raise it); a flow-control handshake output; an element decided at a test letting a flow-control handshake input (or its synchronized copy) hold a transfer.
  Exceptions: judged as usual: those ports, and a setting with an element of none of these kinds (an enable also copied into engine state, clearing a buffer or driving a clock-enable output; a rate setting; a lock; a limit compared with a count).
  Outcome: it is a port option: it only tunes those ports, which carry the effect. A port option is not a piece of its own, although step 2 names each enable, step 3 splits by use and it gates an output port: keep no concept for it, name it in no concept's information, and cite no line assigning it as a held line. A concept also holding a port it tunes stays, for that port alone.
  Evidence: judge from port names which ports are interrupt requests or flow-control handshakes, never a serial link's clock line, and say so.
```

**Phase 2 wording, as tested:**

```
- Port options.
  Scope: a setting a bus write stores.
  Criteria (all of), apart from its read-back: (1) its counterparts show it gives value to or decides some element; (2) each is any of: an interrupt request output (it picks which events raise it); a flow-control handshake output; an element decided at a test letting a flow-control handshake input (or its synchronized copy) hold a transfer.
  Exceptions: judged as usual: those ports, and a setting with an element of none of these kinds (an enable also copied into engine state, clearing a buffer or driving a clock-enable output; a rate setting; a lock; a limit compared with a count).
  Outcome: it is a port option: it only tunes those ports, which carry the effect. A port option never qualifies for any conceptual asset; where 2.6 would make only port options primary, the conceptual asset has none. It can be a secondary to an output port it tunes (2.7, direction b).
  Evidence: judge from port names which ports are interrupt requests or flow-control handshakes, never a serial link's clock line, and say so.
```


---

## P1-24 Per-region checks
Why it was rewritten: over-applied in 4 of 5 sampled one-sided cases: structure only.

**Phase 1 wording, as tested:**

```
- Per-region checks.
  Scope: the per-region or per-entry results.
  Criteria: the unit (1) makes the same compare or permission check per region or entry; (2) only combines the results (a priority chain, an OR) into one decision.
  Exceptions: a per-entry result itself picking where a request goes or which entry an access changes (which port an address selects, which lock is addressed) stays its own piece.
  Outcome: that decision is the piece, held where they combine; the results are its working values (step 3), although step 3 makes a compare of stored state with a request a piece.
```


---

## P1-06 Second copies
Why it was rewritten: over-applied in 3 of 5 sampled one-sided cases: structure only.

**Phase 1 wording, as tested:**

```
- Second copies.
  Scope: an internal register (not a port).
  Criteria: (1) that directly copies bits, not as an index; (2) of one other register of its own entity; (3) whose other assignments write only constants; (4) that no condition reads.
  Outcome: it is a copy kept only while the value moves (2.6), not a piece of its own: name its information under the copied bits' piece, and do not cite its lines as held lines.
```

**Phase 2 wording, as tested:**

```
- Second copies.
  Scope: an internal register (not a port).
  Criteria: (1) that directly copies bits, not as an index; (2) of one other register of its own entity; (3) whose other assignments write only constants; (4) that no condition reads.
  Outcome: it is a copy kept only while the value moves (2.6) and never qualifies as primary for any conceptual asset: the register it copies keeps its own label, and the copy can be a secondary (2.7, direction a).
```

