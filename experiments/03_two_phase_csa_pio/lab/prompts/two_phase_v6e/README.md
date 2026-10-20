# two_phase_v6e: v6 with only the condensing that passed its test (built 2026-10-13, not run)

## What it is

- **The user's request (2026-10-13):** evaluate the pasted suggestions for condensing a prompt, and apply the valid ones
  to v6. The evaluation is in `analysis/prompt_builds/condense_v6/trace/TRACE_V6DE.md`.
- **The suggestions applied:**
  1. "Condense in small isolated steps, test each, keep only the changes that pass, revert the rest." Each of the three
     condensing tracks was run 3 times against v6:
     - Phase 2 (v6b) held: recall was not below v6's lowest run in 2 or more runs, and the element sign test gave
       p 0.79;
     - Phase 1 (v6a) did not hold: its recall reading fired (p 0.004);
     - the shared sentences (v6c) did not hold: both readings fired.

     So **phase1.md and the 35 shared sentences stay v6's**, and **phase2.md keeps v6b's condensing**.
  2. "Protect the words that set a rule's scope." Every Phase 2 unit whose condensed wording has fewer limiting words of
     a class goes back to v6's wording: 9 of v6b's 24 condensed Phase 2 units. The classes are conditions, negations,
     "only", exceptions, "even"-type words, quantifiers, reference words, "also/still" and the spare-list phrases;
     see `trace/protected_register.py`. One of the 9, p2_05.0, is also the only unit the trace kept. The register
     over-flags: of three flagged units read by hand, all three kept their meaning. It is used conservatively, as the
     suggestions advise.
- **Built by** `trace/make_v6de.py` (checks passed: prompt checker, new_format, OUTPUT sections identical to v6, core
  sentences once per file, same line count, restored wording present, phase1.md identical to v6).
- **Words:** phase1.md 6,200 (v6's); phase2.md 7,752 (v6 7,863, so -1.4%).
- **Shas:** Phase 1 `e815598c3dda` = v6's; Phase 2 `189f3a8cc82d`.

## Run design: Phase 2 only, paired with v6

v6e's Phase 1 is v6's, so v6's stored Phase 1 replies are copied in (`prepare_phase1_copy.py two_phase_v6e`, done
2026-10-13: 45 files, byte-identical). Only Phase 2 is sent, and v6e rX is compared with v6 rX on the same concepts.

## Readings (set before the run; compare with v6 r0-r2)

1. **Recall:** 2 or more runs below 0.761 (v6's lowest run) falsifies "this condensing keeps v6's results".
2. **Precision:** 2 or more runs below 0.601 falsifies it.
3. **Paired element losses:** a reference element found by v6 rX but not by v6e rX, in 2 or more runs, is traced and its
   unit restored.
4. **Format:** zero slips.

## What it breaks

Nothing in the reply format. The saving is small, 111 words, and that is what the evaluated method allows on today's
evidence. Further cuts would need new, isolated, tested steps.

## How to run

Notebook cell 9 runs v6d and v6e, 3 runs each. Read the results with
`python analysis/two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2/compare_condensed.py`.

**Cost:** about USD 1.3, Phase 2 only.
