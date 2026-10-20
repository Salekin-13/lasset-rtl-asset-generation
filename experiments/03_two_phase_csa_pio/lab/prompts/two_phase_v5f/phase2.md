THIS CALL: PHASE 2, STRUCTURAL ASSETS (POINTS OF INFLUENCE AND OBSERVATION)

You receive one more input: CONCEPTS, the "Conceptual Assets" list of Phase 1. Each entry has a "Concept ID" (C1, C2, ...), a short name ("Concept Name"), its "Unit", the "Information", the "Objectives At Risk" (C, I, A), the ports it "Enters Through" and "Leaves Through", and the RTL lines where it enters ("Entry Lines"), is stored or produced ("Held Lines") and leaves ("Exit Lines"). Its "Rubric", "Rubric Reason" and "Attack" are Phase 1's answers to Phase 1's questions: use them as context, not as answers to this call's questions.
Treat the list as fixed: analyse every conceptual asset in it, even one you doubt, and do not add, merge or rename any. If you think one is missing or wrong, say so in "Notes"; do not analyse a missing one.

Steps, for each conceptual asset in CONCEPTS:

1. Walk. Work in the diagram of the conceptual asset's unit.
   Start at the blocks that contain its held lines, and at its entry and exit ports (for a port field, at its port). A conceptual asset that is about a clock or a reset itself starts at the blocks whose notes name it and at the instance blocks its arrows reach (2.2). A held line that is a concurrent assignment to an output port outside every generate statement belongs to no block: start at that assignment (see "Points" below). One written inside a generate statement belongs to that [generate] block: start there.
   An arrow from A to B moves the conceptual asset when one of its listed elements carries it (2.2) into B: on a "==>" arrow by an explicit flow, on either kind by an index. It decides the conceptual asset when its listed elements only decide whether, when or where B stores, moves, gates, clears or releases it. Judge each listed element by what it does in B: read its closed-set counterparts whose cited lines are statements of B (B's members, and the output ports or port fields that B's own statements assign; for an [inst] block, B's port-map lines), and read those RTL lines. One element can carry different information on different lines, for example a bus data field that carries settings into one block and other data into another, so do not judge it by its uses elsewhere. The brackets can miss an element; the counterparts and the RTL show it. For an arrow from a block into an output port, with or without brackets, also judge the "gets value from" and "decided by" partners of the port, or of its fields for a record port, whose cited lines are statements of A, wherever those partners are assigned. An arrow from an [inst] block into an output port is a port-map write when it has no brackets or when its brackets name a port of the instantiated entity: for an instance of another IP the black-box rule decides; for an instance of this file, judge that port by its entry in the child entity's list.
   Forward: from an entry port or a holding block, follow the arrows that move the conceptual asset, and keep walking from each block they reach. An arrow whose elements carry the conceptual asset into a block that only tests them (a condition or a case selector) also reaches that block: list it as a point, but do not walk on from it.
   Backward: from an exit port or a holding block, follow backward the arrows that move it, and keep walking back from each block they come from. An arrow into a block on the walk makes its source block an influence point in two cases: its elements only decide the conceptual asset, or they are values from which the block computes the conceptual asset (an operand of an AND, an OR, a compare or a sum) without carrying it. List that block as a point, but do not walk back from it.
   Instances of another IP: when the conceptual asset enters one, every element the instance drives carries it (the black-box rule of section 1). Follow the arrows out of it that list those elements, and say in each point's "Answer Reason" that this is the assumption. Go one instance deep.
   Do not follow an arrow for a clock or reset it lists: it carries no value (2.2). Stop at the unit's ports, and where no arrow moves or decides the conceptual asset any further.
   Points: every block reached this way is a point. A concurrent assignment to an output port that belongs to no block (shown by an arrow with brackets into an output port from a [process], [generate] or [logic] block, or from an [inst] block whose brackets name a signal of the unit rather than a port of the instantiated entity, or by an arrow from an input port straight into one) is a point too; name it after that output port, as OUTPUTS writes it. The unit's ports themselves are where the walk starts and ends; they are not points.

2. Questions. For every point, answer the four questions below for this conceptual asset:
   Confidentiality (the point as an observation point). Does the point expose the conceptual asset: can its value be read out, or inferred, there?
   Integrity (the point as an influence point). Does the point allow any modification of the conceptual asset?
   Availability. Can the point prevent the conceptual asset from being available for functional operation?
   Undermined expected behavior. Does the point have a special behavior, such as a privileged mode, an override, a bypass or test-packet injection, that can prevent the conceptual asset from being available for normal operation? A special behavior that changes the conceptual asset itself is answered under integrity.
   Assume the question's objective as section 3 says. A question whose objective Phase 1 did not list for this conceptual asset is answered "no": confidentiality needs C, integrity needs I, availability and undermined expected behavior need A.
   A "yes" needs a mechanism that the RTL shows, or that the black-box rule gives; cite its line. Judge by 2.9: at a point that stores or sets the conceptual asset, follow its last bullet; at any other point, follow the bullet before it. When every answer is "no", say why.

3. Structural assets. At every point with at least one "yes", name the closed-set elements that store, carry, produce or control the conceptual asset there:
   - the members of the block that do so. At a block that is a point only because an arrow out of it reaches the walk (an influence point), these are the members that this arrow lists, and any the counterparts show the brackets missed. A member that acts on the conceptual asset only through another member is not named here;
   - the unit ports the block reads the conceptual asset from, and the output ports that its arrows reach with the conceptual asset;
   - at a concurrent assignment to an output port: the output port, or the field of it, that the assignment writes, and the input ports, or fields, it reads the conceptual asset from.
   Name the element that carries this conceptual asset: a record field when only that field carries it, even when the RTL also assigns or wires the whole record; the whole record or port only when every field it uses carries it. A unit port that only decides at this point (an enable, a strobe, an address) is not named here; step 5 checks it.
   When the point reads or writes the same field of several unit ports of one role (ports that differ only by an index), write one row for the lowest-numbered port and list the others in "Same Role", each by its exact closed-set name; never shorten that list.
   Each port in the conceptual asset's "Enters Through" and "Leaves Through" lists is a structural asset of it: name it at the point that reads or writes it, even when every answer there is "no"; step 4 labels it by 2.6.
   Each element named here is a structural asset of this conceptual asset. If the conceptual asset passes from a port to a port with no point between them, say so in "Notes".

4. Primary. Among the structural assets of step 3, label primary each element that 2.6 makes primary for this conceptual asset: where its value is stored or computed in this unit, where it crosses the unit's boundary whole, or, for a decision or setting, the element that holds or makes it. A bus request or response record port, or any field of one, never qualifies (2.6), even when it is the only port the conceptual asset enters or leaves through. If none qualifies for a conceptual asset, give the reason in its "No Primary Reason". Any other element that 2.6 says is not primary never qualifies either, even where this step's clause on a decision or setting would make it one.

5. Secondary. For each primary, check the other structural assets of step 3, and the primary's direct counterparts in the closed set, its "clocked by" and "reset by" partners included. Take a "gets value from" or "gives value to" partner when its cited lines are lines where the primary carries this conceptual asset. Take a "decided by" or "decides" partner when the test on its cited line decides such a line; that cited line is the test, which is usually not the line it decides. Take a "clocked by" or "reset by" partner of the primary when an attacker could plausibly use it to stall, block or clear the primary (2.7, direction b). Also take the "decided by" partners of each structural asset that carries the primary's value out of the unit, at the lines where it carries this conceptual asset: they decide the release (2.7, direction b), and they include the deciding unit ports that step 3 leaves out. When an instance of another IP sets the primary, the closed set shows only the instance's own port on that side: then also check the elements wired into that instance's other inputs, citing the port-map lines, and name the instance in its "Justification". Label secondary each one that meets 2.7, and list under its "Secondary To" each primary it serves: that primary's name and entity, and the direction (a or b). A direction counts only for an objective the conceptual asset has (2.7). A structural asset of step 3 that is neither primary nor secondary is not reported in "Assets"; list it under "Not Reported" with the reason.

Rules:
- List every point you reach in "Points", including the points where every answer is "no", so that each step of the walk can be checked against the arrows you followed.
- Report each (element, conceptual asset) pair once. An element can appear under several conceptual assets, with a different label for each.
- Report only closed-set elements, under the constraints of section 1.

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
For a primary, "Secondary To" is an empty list, and "Security Objectives" are those of the "yes" answers at its points (confidentiality gives C, integrity I, availability and undermined expected behavior A). For a secondary, "Security Objectives" are the ones its "Secondary To" entries threaten: C for direction a; for direction b, the objective 2.7 gives it among the conceptual asset's objectives.
