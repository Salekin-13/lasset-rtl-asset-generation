# two_phase_v5 — v4a + basis rules + precision restrictions (2026-10-12, not run)

Base: `two_phase_v4a`, **inputs v1** (user decision: the exact key line of inputs v1k stays out). Built by `analysis/prompt_builds/make_v5.py`; checked by `check_v5.py` (PASS: corpus names, numeric hints, OUTPUT block identical to v4a, the 14 protected phrases kept, rule heads in order, all 34 edits present) and `check_lab_prompt.py` (clean).

System prompts: Phase 1 41,136 chars, sha12 `95761173e1f5` (v4a 32,278, `b13686bbccbf`); Phase 2 37,724 chars, sha12 `0c8ce85ae8d9` (v4a 35,937, `1c69fe88de91`). phase1_user.md and phase2_user.md are byte-identical to v4a.

## What it is for

Raise precision without losing correct finds. On the stored v4a replies, if the model follows every rule, a blind test (two judges per module who did not know which concepts were right; a benefit counts only when both agree, a loss when either reports it) estimates:

| | r0 | r1 | r2 |
|---|---|---|---|
| v4a precision (measured) | 0.294 | 0.285 | 0.321 |
| A + B rules | 0.357 | 0.353 | 0.366 |
| A + B + U (all of v5) | 0.519 | 0.503 | 0.540 |
| extra concepts removed or emptied (of 56 / 68 / 75) | 37 | 49 | 54 |
| false positives removed (of 226 / 211 / 199) | 139 | 128 | 119 |
| correct finds lost | 0 | 0 | 0 |

These are arithmetic on stored replies, not a prediction: the test cannot see false positives a rule might create, and the model may not follow every rule. Recall is unchanged in the estimate; K1 is expected to add csr_rdata in the two runs that miss it (both judges), K2 may add trng valid_o (not measurable by the blind test) and cpu lsu_mar (one judge).

## The rules

Category: **A** published or design-principle basis; **B** no published basis, user decision 2026-10-12; **U** user decision 2026-10-12, reference convention, *removed to increase precision* (restricts prompt lines that produced extra concepts the reference does not list and that contributed no correct find). Estimates: false positives removed / correct lost per run.

| id | cat. | file | what it does | basis or decision | FPs removed | lost |
|---|---|---|---|---|---|---|
| R1 | A | phase2.md | A bus request or response record port, or any field of one, never qualifies (2.6), even when it is the only port the conceptual asset enters or leaves through. | Confirmed this session. ASSET_DEFINITION.md section 3, file line 60, row 'Bus-transaction ports are secondary': '0 of 118 transaction ports,... | 35 / 45 / 19 | 0 / 0 / 0 |
| R4 | A | common.md | An internal element that only passes the value on between two of these (a forwarding wire, a synchronizer stage re-sampling an input port's value, a copy kept o... | Confirmed this session. ASSET_DEFINITION.md section 3, file line 58, row: a register that 'holds a value only while moving it between its en... | 4 / 4 / 4 | 0 / 0 / 0 |
| R7b | B | phase1.md | - Clocks and resets. Clock and reset inputs, a reset request that the unit only combines, gates, registers or passes on to a reset chain or reset output port (i... | None published. ASSET_DEFINITION.md section 3, file line 62 (reset generation: basis none; lives in: evaluation layer). Putting it in the pr... | 8 / 7 / 9 | 0 / 0 / 0 |
| R2b | B | phase1.md | - Pacing pulses. A tick, edge pulse or divider count made inside the unit only to pace another step, or an input port whose only use is a condition letting such... | None published. Diagnosis E8 in the v3 proposal (two_phase_v2 p1_rules/changes_final.json, entry C13) found no basis for a tick-input clause... | 1 / 0 / 3 | 0 / 0 / 0 |
| R5 | A | phase1.md | So is a record this unit only wires between one of its ports and the port map of an instance of another IP, with no statement of this unit reading or writing it... | Confirmed this session. ASSET_DEFINITION.md section 3 rows 'Pure carriers are secondary' (file line 59) and 'Bus-transaction ports are secon... | 6 / 0 / 0 | 0 / 0 / 0 |
| R3 | A | phase1.md | - Working values. Partial results inside a computation (a partial sum, product or round value, a synchronizer stage, a debiasing step) are part of the result th... | IEEE P3164 white paper 3.1.2, p.10: structural assets of a value are "the RTL code that produces "Data" and stores and transports its value"... | 3 / 1 / 1 | 0 / 0 / 0 |
| K2 | A | phase1.md | - Hand-offs. A wait or fault flag, a write-enable flag, or an access address that one instance outputs on a non-record port and hands to another instance or to ... | ASSET_DEFINITION.md section 3, row 1 (file line 55): state, setting and decision elements are primary in their own right (SA-EDI Table 2 'Co... | 0 / 0 / 0 | 0 / 0 / 0 |
| K1 | A | phase1.md | - Register read-back. In a unit executing instructions, the word an instance outputs for reads of its control and status registers, when a statement of this uni... | IEEE P3164 white paper 3.2.3, p.15 (AES example, paraphrase): the status registers are named a conceptual asset of their own, because what t... | 0 / 0 / 0 | 0 / 0 / 0 |
| U1 | U | common.md | the element holding or making that decision is a primary. A stored enable bit whose only use, apart from a read-back, is to choose which events raise an interru... | user decision; restricts: common.md line 97 (present in v4a and v5): 'When the conceptual asset is itself a decision or setting (a lock state, a m... | 9 / 9 / 9 | 0 / 0 / 0 |
| U2a | U | phase1.md | hands to another instance or to this unit's logic is its own piece (step 2), unless Port buffers covers it (then this rule does not apply).... | user decision; restricts: phase1.md line 29 (Hand-offs, present in v5): 'A wait or fault flag ... that one instance outputs on a non-record port a... | (part of U2) | |
| U2 | U | phase1.md | - Port buffers. If the write data of a FIFO instance is a unit input port's value (a bus write, or bits shifted in from a serial input port), the FIFO only buff... | user decision; restricts: phase1.md line 29 (Hand-offs, present in v5): 'A wait or fault flag ... that one instance outputs on a non-record port a... | 18 / 18 / 22 | 0 / 0 / 0 |
| U3 | U | phase1.md | - Serial engines. In a unit that shifts data bit by bit onto or off a serial data port, paced by the unit's own rate setting, the engine doing it only decides w... | user decision; restricts: phase1.md line 7 (step 2): 'Name state the unit holds ...: a mode, a lock, a count, a stored setting, a state machine's ... | 13 / 9 / 11 | 0 / 0 / 0 |
| U5 | U | phase1.md | - Cached copies. In a cache (a unit answering a read from its own copy when a stored tag matches the address, and otherwise fetching the words over a backing bu... | user decision; restricts: common.md line 148 (4.4): '- Shared structures: caches, buffers, register files.' phase1.md line 12 (confidentiality): '... | 12 / 12 / 6 | 0 / 0 / 0 |
| U7 | U | phase1.md | - Operation selectors. In a unit that executes an instruction or an atomic memory operation a processor issues to it (a coprocessor, an atomic read-modify-write... | user decision; restricts: phase1.md line 5 (step 1: 'commands, requests and their responses'), line 7 (step 2: 'each enable, select, override or l... | 4 / 4 / 4 | 0 / 0 / 0 |
| U9 | U | phase1.md | - Per-region checks. When the unit makes the same compare or permission check per region or entry and only combines the results (a priority chain, an OR) into o... | user decision; restricts: phase1.md line 9 (step 3, present in v5): 'A compare of stored state with a request, a count with a stored limit, or a w... | 2 / 0 / 0 | 0 / 0 / 0 |
| U10 | U | phase1.md | - Arbitration bookkeeping. A register that only remembers a request's lock flag while that locked sequence lasts, or the previous grant for round-robin priority... | user decision; restricts: phase1.md line 7 (step 2): '... a mode, a lock, a count, a stored setting ...' and 'each enable, select, override or loc... | 3 / 2 / 3 | 0 / 0 / 0 |
| U4 | U | phase1.md | (a reset shift register, a registered copy of a reset), are not conceptual assets under any question. The clock line of a serial link that the unit drives to, o... | user decision; restricts: phase1.md line 25 (Pacing pulses, v5 wording): '... unless an output port carries that pulse itself (2.2)'. This kept sp... | 9 / 9 / 8 | 0 / 0 / 0 |
| U8 | U | phase1.md | and so is a decision triggering a reset (such as a timeout), where it is computed. A decision that a write was refused or carried a wrong value (a write while l... | user decision; restricts: phase1.md line 23 (R7b, present in v5): '... and so is a decision triggering a reset (a timeout, a violation), where it ... | 3 / 3 / 3 | 0 / 0 / 0 |
| U6 | U | common.md | Label primary the element inside the unit that the access sets, decides or returns. A record that one instance of another IP drives whole and this unit wires wh... | user decision; restricts: common.md line 97, outward clause ('outward, the instance output this unit then uses as the value itself') and decision ... | 14 / 10 / 20 | 0 / 0 / 0 |
| U11 | U | phase1.md | no element of the IP can change or withhold it at run time. So is a run-time bit that a statement ANDs with a build-time switch and whose effect includes writin... | user decision; restricts: phase1.md line 24: 'Instead, name the run-time decision using it as its own concept ...'. The simulation bit looks like ... | 1 / 1 / 1 | 0 / 0 / 0 |
| U12 | U | phase1.md | Merging the bus responses of several ports into one (an OR or a multiplexer) is still forwarding. So is a register stage that captures a whole request or respon... | user decision; restricts: phase1.md line 26: '... that the unit only forwards ... without storing, computing or deciding it, is not a conceptual a... | 0 / 2 / 0 | 0 / 0 / 0 |

## Conflict fixes (F1-F9: three skeptics and a merger, wf_aa7e8d3b-38a; F10-F13: a final verifier, wf_741bb2f0-1be)

Applied after the rules, in this order. Only F2 changes a rule's scope: it gives Phase 2 the per-region rule (U9) that only Phase 1 had; included by default because the U9 blind test already counted that effect (no correct find lost) — the user may veto it.

| id | file | kind | change | reason |
|---|---|---|---|---|
| F1 | common.md | literal conflict | or between a unit port and one such instance, so that the RTL cannot show what it is, or when a later rule says to judge it from port names, for that rule's case only.... | This is one edit. It makes K1's citation true and allows U1's and U2's name judgements, and it opens name use nowhere else. The two skeptics proposed near-identical wordings. I kept C3's wording because 'for that rule's ... |
| F2 | common.md | scope gap or overlap (changes scope) | it can be a secondary linked to that output (2.7, direction b). When a conceptual asset that is a decision only combines the results of the same compare or permission check made pe... | This gives Phase 2 U9's own boundary in U9's own words, including its spare for a result that picks a route or an entry. fail (where the results combine, cpu_pmp 354) and fault_o (where the result is stored, cpu_pmp 363)... |
| F3 | phase2.md | literal conflict | If none qualifies for a conceptual asset, say why in "notes". Any other element that 2.6 says is not primary never qualifies either, even where this step's clause on a decision or ... | The fix states no new scope. It only says that 2.6's own exclusions win over step 4's summary, so it carries U1, U6 and F2 into step 4 at once. It is placed after R1's sentence, so R1's new text stays contiguous and chec... |
| F4 | phase1.md | literal conflict | and so is a decision triggering a reset (such as a timeout), where it is computed, except as the next sentence says.... | This makes U8's carve-out explicit and does not change its reach. cnt_timeout stays covered by 'such as a timeout'. The anchor lies inside U8's text. R7b's other parts are unchanged, so check_v5 still finds R7b and U8 (s... |
| F5 | phase1.md | literal conflict | only time, gate, clear or report on that data: they are not pieces of their own, although step 2 would call some of them a decision.... | The fix names the step it overrides, in R3's wording. U2's If-test and its spares are untouched, so the trng FIFO (generated data) stays outside the rule. The anchor lies inside U2's text, so check_v5 counts U2 as presen... |
| F6 | phase1.md | combined effect on a correct find | its fill flag and its push, pop, clear and enable controls are judged as usual.... | One added word makes the spare list match the roles Port buffers folds. U2a then cannot be read as switching K2 off for the generator's valid flag. Coverage does not change, because the If-test already excludes this FIFO... |
| F7 | phase1.md | literal conflict | the busy and done flags made from them. Do not cite their lines as held lines, except a line assigning an element this rule judges as usual.... | The two skeptics found the same issue. This uses skeptic 1's wording, the same as F9. Only lines that assign a spared element become citable (twi 239, and the spi irq_o assignment). Lines that assign the engine state, co... |
| F8 | phase1.md | literal conflict | are part of that operation (step 3), not pieces of their own, although step 2 names a select.... | The fix names the overridden step, as U3 does ('although step 2 names a state machine's state and a count'). It does not change which fields U7 covers. It touches different text from F9, and both anchors stay unique (sim... |
| F9 | phase1.md | literal conflict | Do not list them under "enters through" or cite their lines as held lines, except a line assigning an element this rule judges as usual.... | The two skeptics found the same issue. This keeps skeptic 1's wording ('this rule judges as usual'), which also covers U7's plain-bus sentence, and matches F7. Lines that make a spared element become citable (muldiv 148-... |
| F10 | common.md | literal conflict (remains after F1) (final verifier) | for another IP, the port name is the only evidence, usable for this purpose alone, apart from the second exception under "Constraints on the inputs" below.... | Line 40 limits how an instance of another IP may be judged by its port names: "for another IP, the port name is the only evidence, usable for this purpose alone" (the purpose is spotting a clock or reset). Two Phase 1 ru... |
| F11 | phase1.md | literal conflict (same pattern as F5 and F8) (final verifier) | none of them is a piece of this unit, although steps 1 and 2 would name them and 4.4 names caches.... | Cached copies (U5, line 33) says the copied words and the tag and valid bits are not pieces: "none of them is a piece of this unit, although 4.4 names caches". Step 1 (line 5) says to name "data received, held or returne... |
| F12 | phase1.md | broken sentence (from rule edit U11, not one of the 9 fixes) (final verifier) | Nor is a run-time bit that a statement ANDs... | The sentence before it is negative: "A generic or constant that only fixes the build ... is not a conceptual asset". U11 then continues with "So is a run-time bit that a statement ANDs with a build-time switch ...". "So ... |
| F13 | phase1.md | corpus identifier (plain words; passes the code check) (final verifier) | its fill flags (whether it holds data or has room),... | Port buffers lists the fill flags as "(available, free, half)". This matches the corpus FIFO one-for-one: neorv32_fifo RTL line 55 declares "signal we, re, match, empty, full, half, free, avail", with ports avail_o, free... |

## Decisions recorded (also in EXPERIMENT_LOG.md section 11)

- B rules R2b (an input only letting a tick advance is a pacing pulse) and R7b (reset requests only passed to a reset chain are not assets): no published basis; user decision 2026-10-12.
- U rules U1-U12: user decision 2026-10-12, quoted: "if reference doesn't list them, and they don't emit or contribute to any TP, then remove them and keep the decision with reasoning in the log. That it was removed to increase precision." Each passed the blind test with no correct find lost.
- Inputs v1, not v1k: user decision 2026-10-12.

## What it breaks

- All three system files change (Phase 1 reads common.md + phase1.md, Phase 2 reads common.md + phase2.md): v5 is compared only with its own reruns and with v4a (same model, effort, inputs, three runs).
- phase1.md almost doubles (1,448 -> 2,790 words). v2a and v4a showed brevity alone does not change scores; length growth of this size has not been tested, so a compliance drop is possible.
- The U rules fit the prompt to this reference's conventions. They may remove information that other references, or the held-out modules, keep.

## How to read the run (falsification)

- Precision: falsified if v5's precision is not above v4a's run range (0.285-0.321) in at least two of three runs.
- Recall: falsified (rules removed too much) if any reference element found in all three v4a runs is found in fewer than two v5 runs, or if recall falls below v4a's range (0.771-0.862).
- Per rule: the 'risk' and 'falsified if' notes of each rule in RULES_PROPOSAL.md and u_workflow_result.json name the elements to read.
- Overfitting: run v5 and v4a on the 26 held-out modules; if held-out recall drops against v4a, the U rules remove information the reference keeps elsewhere.

## Run it

Notebook `final/pio/pio_pilot.ipynb`: cell 1 `INPUT_VERSION = "v1"`; cell 9 `JOBS = [("two_phase_v5", r) for r in (0, 1, 2)]`, `RUN_MANY = True`. Runs go to `runs/two_phase_v5__v1/gpt-5.6-luna__high/r<k>/`.

Full rule texts: phase1.md, common.md and phase2.md here; reasons, bases, what each spares and risks: `analysis/two_phase_v4a__gpt-5.6-luna__high__r0-r2/RULES_PROPOSAL.md` (A, B) and `u_workflow_result.json` (U).
