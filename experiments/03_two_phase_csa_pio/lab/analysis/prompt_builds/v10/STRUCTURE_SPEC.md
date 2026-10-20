# v10 rule rewrite: specification for writers and checkers

Base: `prompts/two_phase_v9` (phase1.md rules list; phase2.md step 4, line 34, one sentence per S-id in the dossiers).
User request (2026-10-15): fix the wording of rules that the isolation test found read two ways; give the critical rules a
clear structure and decision order; keep word counts down; do not increase a rule's words unless absolutely necessary.

## 1. Two jobs per rule, in this order

1. **Reword** (only rules marked "reword" in the dossier). Change the smallest span that removes each documented two-way
   reading. Keep the rule's intent. Every change must point at a documented case (dossier evidence) and say which reading
   the new words choose, and why that reading follows from the rule's own purpose or the prompt's definitions (2.x, step
   names). Do not narrow or widen a rule because a reference answer list contains or omits a signal: you have no such list
   and must not reason from one.
2. **Structure** (every rule in the dossiers). Reorganize the (reworded) rule into the slots below, using the rule's own
   words. Allowed additions: the slot labels, "all of" / "any of", "(1)", "(2)" numbering, "if" / "then", and a noun that
   replaces a pronoun whose referent moved away. Allowed removals: connectives the slots make redundant ("while", "so",
   "and so is", "although"). Everything else stays word for word. The checker (section 5) lists every added and dropped
   word.

## 2. The structure (improved from the user's draft)

The user's draft order was scope, decision criteria, procedure, evidence, exception boundary. Changes and why:
- Exceptions come right after the criteria, before the outcome: in the isolated runs the model applied the criteria and
  did not reach exceptions written at the end (e.g. it barred a busy flag that Sequencing state's exception keeps).
- The procedure is the same for every rule, so it is written once (section 3), not in each rule. Each rule keeps only
  its own "Outcome": what follows when it applies (and, for a rule with sub-cases, what follows in each case).
- Criteria say whether all or any must hold.
- "Evidence" appears only when the rule already names what to judge from or what to cite (port names, held lines).

Phase 1 block (in the rules list of phase1.md):

    - <Title>.
      Scope: <which units and which elements the rule looks at; units it leaves out>.
      Criteria (all of): (1) <...>; (2) <...>.            [or "(any of)" for alternatives; nest "any of" inside a criterion if needed]
      Exceptions: <cases the rule does not cover or judges as usual>; <...>.
      Outcome: <what follows: e.g. "not a piece of its own: keep no concept for it ..."; one "If <case>, <result>." per sub-case>.
      Evidence: <only if the rule names it: "Judge from port names which ports are ..., and say so"; lines to cite or not cite>.

Phase 2 block (in step 4 of phase2.md): the same slots. Scope, Criteria and Exceptions use the same words as the Phase 1
block wherever the v9 wordings share them (they mostly do); Outcome carries the Phase 2 result ("never qualifies for
any conceptual asset", "can be a secondary only in direction b (2.7)", "where 2.6 would make only these primary, the
conceptual asset has none").

A rule with independent parts (e.g. a bar and a separate "is its own piece" clause) may use one block per part, titled
"<Title> (a)", "(b)". A sub-clause that only says where another rule takes over stays in Exceptions.

## 3. The shared procedure (written once, by the assembler, not in each rule)

Phase 1, after "Precedence":
"- Reading a rule. Check its scope, then each criterion, then each exception, in that order. Its outcome follows only for
an element in scope that meets the criteria and that no exception covers; a criterion that the RTL, or the evidence the
rule names, does not show is not met."
Phase 2, at the start of the bars in step 4: the same sentence.

## 4. Word budget

- Reworded flat text: at most the v9 words of that wording, plus at most 10% where a fix needs words; say why for every
  added word group.
- Structured text: at most the reworded flat text's words, plus the slot labels. Remove redundant connectives to pay
  for the labels where you can.
- Report: v9 words, reworded words, structured words, for each wording.

## 5. Checks (run them; the checker is code)

    python E:/jobs/ff/test/Prepoison_subset/final/pio/lab/analysis/prompt_builds/v10/check_rule_draft.py <draft.json>

`<draft.json>`: {"<rule id>": {"P1_flat": "...", "P1_structured": "...", "P2_flat": "...", "P2_structured": "..."}}
(omit a phase the rule does not have). It reports word counts, the words the structured text adds or drops relative
to the flat text, missing or out-of-order slot labels, and the project's prompt checks: no corpus identifier (no module,
entity or signal name from the corpus), no numeric emission hint ("at most 20", "%", "at least half"), no instruction
to read comments. A failing project check is a blocker.

## 6. Decisions already taken (apply them)

- D2 Forwarded transactions: merging several ports' bus responses into one with an OR or a multiplexer is forwarding in
  both wordings; the exception for "the value a mixing statement writes" must not cover it.
- D3 Working values: the Phase 1 wording gains the exception that Phase 2 has ("the element holding the finished result
  or that an output port takes it from"), phrased for information (Phase 1 judges information, not elements).
- D4 Operation selectors: start from the v9 wording (the revised scope is dropped).
- D8 Pacing pulses: the Phase 1 bar "an input port used only as a condition letting such a tick or count advance"
  barred a unit input port reduced to an enable that decides whether a divider count runs at all. Step 2 of phase1.md
  makes each enable deciding whether other information is used a decision of its own; reword so an enable input
  deciding whether the count runs is judged as usual, and keep the bar on a pulse or condition that only times a step.

## 7. What to return (writer)

For each rule of the group: the four texts (P1_flat, P1_structured, P2_flat, P2_structured; "same as v9" is not
allowed, write the text); for P2, which S-ids the block replaces and which S-sentences stay where they are (a sentence
inside the general 2.6 or step-5 text may stay, reworded if needed); a change list (old words, new words, the evidence
case ids it fixes, why); word counts; the checker output summary.
