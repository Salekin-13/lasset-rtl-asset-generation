THIS CALL: PHASE 2, STRUCTURAL ASSETS (POINTS OF INFLUENCE AND OBSERVATION)

One more input: CONCEPTS, Phase 1's "Conceptual Assets" list. Each entry has a "Concept ID", "Concept Name", "Unit", "Information", "Objectives At Risk" (C, I, A), the ports it "Enters Through" and "Leaves Through", and its RTL "Entry Lines", "Held Lines" (where it is stored or produced) and "Exit Lines". Its "Rubric", "Rubric Reason" and "Attack" answer Phase 1's questions: use them as context, not as this call's answers, except as step 2 says.
Treat the list as fixed: analyse each entry, even a doubtful one, and add, merge or rename none. Say in "Notes" if one seems missing or wrong; do not analyse a missing one.

Steps, for each conceptual asset in CONCEPTS:

1. Walk. Work in the diagram of the conceptual asset's unit.
   Start at the blocks containing its held lines and at its entry and exit ports (for a port field, its port). A conceptual asset about a clock or reset itself starts at the blocks whose notes name it and at the instance blocks its arrows reach (2.2). Outside every generate statement, a held line that is a concurrent assignment to an output port belongs to no block: start at that assignment (see "Points" below); inside one, it belongs to its [generate] block: start there.
   An arrow from A to B moves the conceptual asset when one of its listed elements carries it (2.2) into B: on a "==>" arrow by an explicit flow, on either kind by an index. It decides the conceptual asset when its listed elements only decide whether, when or where B stores, moves, gates, clears or releases it. Judge each listed element only by what it does in B: read its counterparts whose cited lines are statements of B (B's members and the output ports or port fields B assigns; for an [inst] block, B's port-map lines), and those RTL lines. One element can carry different information on different lines (a bus data field carrying settings into one block, other data into another). Brackets can miss an element; counterparts and RTL show it. For an arrow from a block into an output port, bracketed or not, also judge the port's (for a record port, its fields') "gets value from" and "decided by" partners whose cited lines are statements of A, wherever those partners are assigned. An [inst] block's arrow into an output port is a port-map write when unbracketed or when its brackets name a port of the instantiated entity: for an instance of another IP the black-box rule decides; for one of this file, judge that port by its entry in the child entity's list.
   Forward: from an entry port or a holding block, follow the arrows that move the conceptual asset, and keep walking from each block they reach. An arrow whose elements carry the conceptual asset into a block that only tests them (a condition or a case selector) also reaches that block: list it as a point, but do not walk on from it.
   Backward: from an exit port or a holding block, follow backward the arrows that move it, and keep walking back from each block they come from. An arrow into a block on the walk makes its source block an influence point in two cases: its elements only decide the conceptual asset, or they are values from which the block computes the conceptual asset (an operand of an AND, an OR, a compare or a sum) without carrying it. List that block as a point, but do not walk back from it.
   Instances of another IP: when the conceptual asset enters one, every element the instance drives carries it (the black-box rule of section 1). Follow the arrows out of it that list those elements, and say in each point's "Answer Reason" that this is the assumption. Go one instance deep.
   Do not follow an arrow for a clock or reset it lists: it carries no value (2.2). Stop at the unit's ports, and where no arrow moves or decides the conceptual asset any further.
   Points: every block reached this way is a point, and so is every block whose own statements include one of the conceptual asset's held lines, even when no arrow you follow reaches it. A concurrent assignment to an output port that belongs to no block (shown by an arrow with brackets into an output port from a [process], [generate] or [logic] block, or from an [inst] block whose brackets name a signal of the unit rather than a port of the instantiated entity, or by an arrow from an input port straight into one) is a point too; name it after that output port, as OUTPUTS writes it. The unit's ports themselves are where the walk starts and ends; they are not points.

2. Questions. For every point, answer the four questions below for this conceptual asset:
   Confidentiality (the point as an observation point). Does the point expose the conceptual asset: can its value be read out, or inferred, there?
   Integrity (the point as an influence point). Does the point allow any modification of the conceptual asset?
   Availability. Can the point prevent the conceptual asset from being available for functional operation?
   Undermined expected behavior. Does the point have a special behavior, such as a privileged mode, an override, a bypass or test-packet injection, that can prevent the conceptual asset from being available for normal operation? A special behavior that changes the conceptual asset itself is answered under integrity.
   Assume the question's objective as section 3 says. A question whose objective Phase 1 did not list for this conceptual asset is answered "no": confidentiality needs C, integrity I, availability and undermined expected behavior A. If an entry lacks "Objectives At Risk", the list was left out, not emptied: rebuild it from its "Rubric", as Phase 1 does, and use it wherever this call names the objectives Phase 1 listed. A "yes" to confidentiality gives C, to integrity I, to availability A, and to undermined expected behavior the objective its "Rubric Reason" says the behavior breaks (I if it makes the output incorrect, A if it stops the function).
   A "yes" needs a mechanism the RTL shows or the black-box rule gives; cite its line. Judge by 2.9: its last bullet at a point that stores or sets the conceptual asset, the bullet before it elsewhere. If every answer is "no", say why.

3. Structural assets. At each point with any "yes", name the closed-set elements that store, carry, produce or control the conceptual asset there:
   - the block's members that do so. At a block that is a point only because an arrow out of it reaches the walk (an influence point), these are the members this arrow lists, plus any the counterparts show the brackets missed. A member acting on the conceptual asset only through another member is not named here;
   - the unit ports the block reads the conceptual asset from, and the output ports its arrows reach with the conceptual asset;
   - at a concurrent assignment to an output port: the output port or port field it writes, and the input ports or port fields it reads the conceptual asset from.
   Name the element carrying this conceptual asset: a record field when only that field carries it, even if the RTL also assigns or wires the whole record; the whole record or port only when every field it uses carries it. A unit port that only decides at this point (an enable, a strobe, an address) is not named here; step 5 checks it. When a state machine, apart from reset, changes state only at steps a peer device's clock paces, and its next state depends only on its current state and one bit of a non-record input port (directly or through synchronizer stages), that port, never the peer's clock line, is the input port setting the state (2.6), though only conditions test its bit (an implicit flow, 2.2). Name that port here for the conceptual asset about that state, at the block reading it, although it only decides: walk back to it through those stages even past an influence point (step 1), even if CONCEPTS does not list it under "Enters Through".
   When the point reads or writes the same field of several unit ports of one role (differing only by an index), write one row for the lowest-numbered port and list the others in "Same Role" by exact closed-set name; never shorten that list.
   Each port in the conceptual asset's "Enters Through" and "Leaves Through" lists is a structural asset of it: name it at the point reading or writing it, even when every answer there is "no"; step 4 labels it by 2.6. Before returning the JSON, check that each such port has a row in "Assets" or "Not Reported", and so does each member the first bullet says to name at an influence point (as that bullet defines it) with a "yes"; a whole record's row covers its fields.
   Each element named here is a structural asset of this conceptual asset. If the conceptual asset passes port to port with no point between, say so in "Notes".

4. Primary. Among the structural assets of step 3, label primary each element that 2.6 makes primary for this conceptual asset: where its value is stored or computed in this unit, where it crosses the unit's boundary whole, or, for a decision or setting, the element that holds or makes it. A non-record unit input port (not a clock, a reset, a reset request, a serial clock line, or a port whose bits only become ticks pacing a step) that the RTL copies unchanged into the conceptual asset's value, alone or side by side with other such ports, or reduces to one bit that alone, apart from constants, sets the register holding the conceptual asset (the input port setting it, 2.6), or wires straight into an instance input taking that value, crosses the boundary whole: label it primary for that conceptual asset, not secondary as a path to or a decider of an element computed from it, which keeps its own label; this sentence only adds primaries, so a port it does not cover (such as one the RTL only tests, or reduces to one bit it then mixes with other values) is labelled as if this sentence were absent.
Reading a rule below: check its scope, then each criterion, then each exception it lists, in that order, against the RTL; where a criterion says "only", "every" or "one element", check every assignment or use, not one. Its outcome follows only for an element in scope that meets every criterion (one, where marked "any of") and that no listed exception covers.
Where an accepted compare outcome, an access address or an operand setting is held: the outcome of a compare of a written value with a fixed value is held at the register that the branch taken when the value matches sets, as that register is where the compare is computed (step 3) even when it keeps the outcome for one cycle only and only restarts a counter, so it is neither the action the compare triggers nor a one-cycle request folded into what it times, and the line where the other branch requests a reset is never its held line; an access address that leaves the unit in the address field of a bus request record port, which never holds it (2.6), is also held at each non-record port on which an instance of another IP outputs that address to another instance, judged from the port names at either end (an address output, or an output wired into an address input) as a hand-off; and a setting decoded from instruction fields that changes how operands are read (signedness), not a flag only naming the operation, is held at the lines assigning it, even inside a concept about the operation it belongs to; Phase 1 cites each such line as a held line of the concept whose information it is, and Phase 2, at the block owning each such line, names the element the line assigns, even when no arrow it follows lists that element, and labels it primary for that concept. Each bar in this step (saying an element never qualifies or is not primary) holds even if CONCEPTS names the element, cites its lines as held lines or lists it under "Enters Through" or "Leaves Through", or where 2.6, 2.8 or another sentence would make it primary or 4.4 points at it; a bar worded "for any conceptual asset" also covers a conceptual asset about the element. A barred element can still be a secondary (2.7). What a rule judges as usual or does not cover is spared only from that rule's bar.
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
If none qualifies for a conceptual asset, give the reason in its "No Primary Reason".

5. Secondary. For each primary, check the other step 3 structural assets and the primary's direct closed-set counterparts, its "clocked by" and "reset by" partners included. Take a "gets value from" or "gives value to" partner whose cited lines are where the primary carries this conceptual asset. Take a "decided by" or "decides" partner whose cited line is a test deciding such a line, usually not the decided line itself. Take a "clocked by" or "reset by" partner of the primary that an attacker could plausibly use to stall, block or clear the primary (2.7, direction b). Also take the "decided by" partners of each structural asset carrying the primary's value out of the unit, at lines where it carries this conceptual asset: they decide the release (2.7, direction b), including the deciding unit ports step 3 omits. When an instance of another IP sets the primary, the closed set shows only the instance's port on that side: also check the elements wired into the instance's other inputs, citing the port-map lines, and name the instance in its "Justification". Label secondary each one meeting 2.7, listing under its "Secondary To" each primary it serves: name, entity and direction (a or b). A direction counts only for the conceptual asset's objectives (2.7). List a step 3 structural asset that is neither primary nor secondary under "Not Reported" with the reason, not in "Assets". A conceptual asset with no primary has no secondary, as a secondary names a primary under "Secondary To" (2.7): list all its structural assets under "Not Reported", its "Enters Through" and "Leaves Through" ports included.

Rules:
- List every point reached in "Points", even where every answer is "no", so each walk step can be checked against the arrows followed.
- Report each (element, conceptual asset) pair once; an element can appear under several conceptual assets, each with its own label.
- Report only closed-set elements, under section 1's constraints.

OUTPUT

Return one JSON object:
{
 "IP": "<the module name given in the input>",
 "Concept Walks": [
  {
   "Concept ID": "<an id from CONCEPTS, e.g. C1>",
   "Points": [
    {
     "Point": "<a block name as the ARROWS lines write it (with any ' (line N)' suffix; for an [inst] block, the label without the part in parentheses), or, for a concurrent assignment to an output port, that port's name>",
     "Reached By": "<one sentence: the arrow you followed to this point, or 'holding block', or 'held line'>",
     "Point Answers": {
      "Confidentiality": "yes" | "no",
      "Integrity": "yes" | "no",
      "Availability": "yes" | "no",
      "Undermined Expected Behavior": "yes" | "no"
     },
     "Answer Lines": [<RTL line numbers that show each yes>],
     "Answer Reason": "<one sentence: the mechanism behind each yes, or why none applies>"
    }
   ],
   "Assets": [
    {
     "Asset RTL": "<exact closed-set name>",
     "Entity": "<the entity name that declares it, copied verbatim>",
     "Label": "primary" | "secondary",
     "Same Role": ["<exact closed-set names of the same field of other ports of one role; empty if none>"],
     "Found At": ["<the points where it was found; empty for an element found only as a direct counterpart of a primary>"],
     "Security Objectives": ["C" | "I" | "A", ...],
     "Secondary To": [{"Primary RTL": "<a primary's exact closed-set name>", "Primary Entity": "<its entity>", "Direction": "a" | "b"}],
     "Functionality": "<one sentence: what the element stores, carries, produces or controls for this conceptual asset>",
     "Justification": "<one sentence: why that gives it this label>",
     "Asset Lines": [<RTL line numbers>]
    }
   ],
   "Not Reported": [
    {"Element RTL": "<exact closed-set name>", "Element Entity": "<the entity name that declares it>", "Why Not Reported": "<one sentence: why it is neither primary nor secondary>"}
   ],
   "No Primary Reason": "<one sentence: why no structural asset qualifies as primary; an empty string when one does>"
  }
 ],
 "Notes": ["<one sentence each: an RTL fact that contradicts the inputs, a doubt about CONCEPTS, or a port-to-port path with no point>"]
}
Follow this format strictly: write every key shown, spelled and ordered as shown, in every object, and no other key. Each object starts with its own identifier: "Concept ID" in a walk, "Point" in a point, "Asset RTL" in an asset, "Element RTL" in a not-reported entry.
Give one entry in "Concept Walks" for each conceptual asset in CONCEPTS, in the order CONCEPTS gives, even when its lists are empty.
For a primary, "Secondary To" is an empty list, and "Security Objectives" are those of the "yes" answers at its points (confidentiality gives C, integrity I, availability and undermined expected behavior A). For a secondary, "Security Objectives" are the ones its "Secondary To" entries threaten: C for direction a; for direction b, the objective 2.7 gives it among the conceptual asset's objectives. What sections 1 and 2 put "in the reason" goes in the point's "Answer Reason" or the asset's "Justification".
