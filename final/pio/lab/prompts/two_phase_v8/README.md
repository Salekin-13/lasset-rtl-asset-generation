# two_phase_v8: v7 + seven prompt rules from the v7 failure analysis (built 2026-10-14; NOT run)

**Status:** built and checked (including one combined read-through, whose seven fixes are applied); not run. Nothing below is a measurement of v8 on the model.

## What it is

- **Base:** two_phase_v7, the final prompt. Its 3 runs: precision (correct ÷ listed) 267/435 = 0.614, recall
  (correct ÷ 109 per run) 267/327 = 0.817 (analysis/two_phase_v7__gpt-5.6-luna__high__r0-r2/compare_v7.py).
- **The user's request (2026-10-14):** implement the seven prompt rules of the v7 failure analysis, after resolving the
  conflict between B1 and R5. The four code filters (P1-P4) are held: "the task at hand is prompt debugging".
- **Source:** analysis/two_phase_v7__gpt-5.6-luna__high__r0-r2/failure_analysis/RULES_FROM_V7.md. Each rule was drafted
  by a fresh agent, challenged by two skeptics (evidence and risk), revised, checked in code (no corpus names, no numeric
  hints), checked for conflicts with the others, and blind-tested on the stored v7 replies (2 judges per module, no
  reference). The rule records are failure_analysis/rules/<ID>/revised.json (R5: merged.json).

| Rule | Kind | What it does | Blind test on the stored v7 replies | Words added (phase1 / phase2) | Basis |
|---|---|---|---|---|---|
| B1 | paired | When this unit's decisions read the signal an output port of an instance of this file drives, that signal is primary, not the child port | +3 correct, -3 false positives | 127 / 111 | the prompt's own definitions (2.6 outward clause) |
| R1 | paired | A switch's requests waiting for a grant (one bit per requester) and the strobe the grant drives are information of their own | +8 correct | 190 / 218 | the prompt's own definitions |
| R2 | paired | The sequencing-state bar keeps judging as usual a peer's command input that reaches a state machine through synchronizer stages | +3 correct | 130 / 130 | the prompt's own definitions |
| R3 | Phase 1 | A FIFO holding data the unit generates: its tested holds-data flag and its clear-only command are each their own piece | +4 correct | 88 / 12 (build consistency edit, below) | the prompt's own definitions |
| R4 | Phase 1 | The access address of a memory the unit itself stores is a piece of its own | +2 correct | 206 / 0 | published source (IEEE P3164 white paper, SRAM example) |
| R5 | Phase 2 | A reduced enable input and a plain-copy output port are primary next to the element they set or copy (B1's case excepted) | +4 correct | 0 / 166 | the prompt's own definitions (2.6) |
| R6 | paired | Holds the line of an accepted compare outcome, a handed-off access address and a decoded operand setting | +7 correct | 257 / 251 | the prompt's own definitions |

The blind test lost no correct find and added no false positive for any rule. All 7 together, on the stored replies:
correct 92/89/86 -> 101/100/98, recall 0.817 -> 0.914, precision 0.614 -> 0.644. **This is an upper bound** (see Risks).

## The B1 / R5 conflict, resolved

- **The clash (stage D):** the rule texts decided one case two ways: a non-record output port of an instance of an
  entity of this file that copies a value unchanged into a unit signal which lists "decides" partners. B1 made the
  unit signal primary; R5 made the port primary.
- **Resolution:** R5's main sentence now names B1's case as an exception, inside the sentence: "... and except an
  instance's port whose port-map signal in this unit gets its value from that port and lists "decides" partners (that
  signal is primary instead, by the sentence on a value an instance of this file outputs, or, for a hand-off, by the
  sentences on hand-offs) ...". B1 is unchanged (the hand-off pointer was added by the read-through, fix 4 below).
  Record: failure_analysis/rules/R5/merged.json (+38 words over R5's revision).
- **Why B1 wins this case:** B1 rests on 2.6's outward clause (the instance output this unit then uses as the value
  itself): the unit's decisions use the value through its own signal. R5's targets are not affected: a unit's own
  output ports, and child ports whose unit signal lists no "decides" partner.
- **Measured:** failure_analysis/rules/conflict_scan.py (self-test PASS) scans all 41 closed sets (15 tuning + 26
  held-out). 2 unit signals meet B1's condition, both in tuning modules, and neither child port is a plain copy, so 0
  elements meet both. The exception changes no element of the blind test.

## Build decisions

- **R3 consistency edit:** R3 edits the main sentence of the status-bit bar on phase1.md (v7 line 38). The same
  sentence is on phase2.md (v7 line 34), so the build applies the same edit there, to keep the sentence shared by both
  phases, as every v7 shared sentence is. Phase 2's own trailing list already spares that flag, so the meaning of
  Phase 2 does not change.
- **Order:** B1's and R6's new Phase 1 bullets both go after v7 phase1.md line 32 (the hand-off bullet), in that order.
  R1's new Phase 2 paragraph goes after v7 phase2.md line 34.
- **Built by:** analysis/prompt_builds/v8/make_v8.py (dry run first; every replace is anchored to its v7 line and must
  occur exactly once there).

## Read-through fixes (applied; make_v8.py REVIEW)

One agent read the assembled v8 (report only, 2026-10-14). Each claim was checked against the text before the fix was
applied. The fixes change wording, not what a rule covers:

1. After R2's new clause, "It and its internal busy and done flags" could point at the port or the command: now
   "Sequencing state and its internal busy and done flags" (both phase files).
2. R1's "do not cover them" could point at the lock bits R1 just left out: now "do not cover such a register or that
   strobe signal".
3. Phase 2's trailing list repeated the FIFO-flag exception the consistency edit put in the main sentence: removed
   there (Phase 1's copy was already removed by R3).
4. R5's exception now also points to the hand-off sentences for a hand-off.
5. B1's held line yields to the Port buffers rule ("unless the Port buffers rule bars citing that signal's lines").
6. R6's Phase 2 sentence moved after B1's, so the hand-off sentences stay together and the order matches Phase 1.
7. R3: "the flag held at the line wiring it out of the FIFO, with the read-data line returning the flag as its exit".

Not changed (reported as low and checked): R4's pointer "which Held addresses bars" matches only the "Held
addresses" bullet.

## Checks passed (make_v8.py)

- The project prompt checker (check_lab_prompt.check: corpus identifiers, numeric hints, comments, the final-JSON
  phrase, both user templates): clean; its planted self-test caught all 3 problems.
- chain.new_format for both phases.
- The OUTPUT sections byte-identical to v7; common.md and both user templates identical to v7.
- All 32 sentences (6+ words) that v7's two phase bodies share are still in both.
- Every paired rule's core sentence is in both phase bodies; every edit's new text is in its file.
- **Words:** phase1.md 5,963 -> 6,979 (+1,016, +17%); phase2.md 7,573 -> 8,461 (+888, +12%); common.md unchanged.
- **Shas:** Phase 1 `88a651707c04`, Phase 2 `b61510131dbf` (v7 `be3b3faab49b` / `6e414c09e397`). Both change: full runs.

## Readings (set before the run; read with analysis/two_phase_v8__gpt-5.6-luna__high__r0-r2/compare_v8.py)

Compare with v7 r0-r2 only, never pooled with another version. compare_v8.py's self-test reproduces v7's
92/89/86 correct of 146/158/131 listed. Phase 2 alone moves a run by 0-5 correct finds on fixed concepts (measured
2026-10-13, v6abc spread test), so smaller differences are not read as effects.

1. **Recovery:** of the 10 target elements found in at most 1 v7 run (bus a_req, b_req, stb; cache cache_i.sta_hit;
   cpu lsu_mar; debug_dtm jtag_tms_i; imem addr; sys enable_i; trng fifo.avail; wdt reset_wdt), at least 5 found in
   2 or more of 3 v8 runs supports the rules. **Fewer falsifies them.**
2. **Recall:** recall below 86/109 (v7's lowest run) in 2 or more runs **falsifies** "v8 does not cost recall";
   above 92/109 (v7's highest) in 2 or more runs supports a gain.
3. **Precision:** below 89/158 = 0.563 (v7's lowest run) in 2 or more runs **falsifies** "v8 keeps v7's precision".
4. **B1:** the child hit output listed primary in 2 or more runs, or the parent hit field found in at most 1, falsifies
   B1.
5. **Element losses:** any element found in all 3 v7 runs and in at most 1 v8 run is read as a rule applied beyond its
   text (v6's failure); compare_v8.py lists them, and the new false positives no v7 run listed.
6. **Per-rule falsifiers:** each rule record's "falsifier" field (RULES_FROM_V7.md section 4).
7. **Held-out (26 modules, 187 findable elements):** needs v7 and v8 runs on them (compare_v8.py --heldout). v8's
   pooled recall or precision below v7's on the held-out modules would show the rules fit the tuning modules only.

## Risks (reasoning, with the measured history)

- **The blind test is an upper bound.** Earlier blind tests were optimistic: v5g predicted precision 0.50-0.55 and ran
  at 0.43; v6 predicted 0 lost correct finds and lost 10 elements (HANDOVER.md, V6_RESULTS.md). The model skips
  exceptions and applies bars beyond their text, and a new Phase 1 can drop concepts the stored replies still have.
- **Narrow rules.** The two blind judges made the same changes on every module. B1 meets its condition at one element in
  the 41 closed sets (conflict_scan.py); R1 fits the one switch of the corpus; R4 one memory. They may not generalise:
  reading 7 tests that.
- **Length:** +17% and +12% per phase file. v6's growth came with rules applied beyond their text.

## How to run (paid; the user decides who sends it)

- **Tuning (15 modules):** notebook final/pio/pio_pilot.ipynb, cell 9: `JOBS = [("two_phase_v8", r) for r in (0, 1, 2)]`,
  `RUN_MANY = True`. Restart the kernel and run cell 1 first. 90 calls; estimate about USD 2.2 (v7's 3 runs cost USD 2.18
  from their stored usage; v8's system prompts add about 121k input tokens over 3 runs).
- **Held-out (26 modules):** cell 1 `ALL = K.gt_modules()["heldout"]`, and in cell 9 the jobs of both versions:
  `JOBS = [("two_phase_v7", r) for r in (0, 1, 2)] + [("two_phase_v8", r) for r in (0, 1, 2)]`. 312 calls; rough
  estimate USD 4.1 for v7 and 4.2 for v8 (input from the message sizes; output borrowed from v7's tuning runs, scaled
  by message size; the largest held-out message is 4.6 times the tuning mean).
- **Afterwards:** `python final/pio/lab/analysis/two_phase_v8__gpt-5.6-luna__high__r0-r2/compare_v8.py` (and `--heldout`).
