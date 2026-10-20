# two_phase_v6abc: v6 with all three condensing tracks combined (built 2026-10-13, not run)

## What it is

- **Base:** two_phase_v6. It combines v6a (phase1.md condensed), v6b (phase2.md condensed) and v6c (the 35 shared core
  sentences condensed, the same text in both files). The tracks edit text that does not overlap, so the combination is
  a plain replacement, with no merge step.
- **The user's request (2026-10-13):**
  - condense Phase 1 and Phase 2 and their shared core sentences, with the same instruction meanings in fewer words;
  - use less vague words and shorter, specific sentences;
  - condense as much as possible without lowering the model's performance;
  - give one blind boundary test, on the combined version.
- **Built by:** `analysis/prompt_builds/condense_v6/` (report: `CONDENSE_V6.md`).
- **Checks passed:**
  - phase1 pieces 9 of 9, phase2 pieces 10 of 12 (p2_02 and p2_08 keep v6's text), core sentences 35 of 35;
  - OUTPUT sections, common.md and both user templates are byte-identical to v6;
  - each core sentence occurs once in each phase file;
  - the project prompt checker is clean, and `chain.new_format` reads the format;
  - a read-through (wf_783a745d-545) found no broken cross-references or joins.
- **Words:** phase1.md 6,200 -> 5,866 (-5.4%); phase2.md 7,863 -> 7,408 (-5.8%).
- **Shas:** Phase 1 `4a1d22d55f30`, Phase 2 `560157f08368`. Both change, so this version needs full runs.

## Blind boundary test (wf_783a745d-545, 30 judges, on this exact text)

The judges applied the text to v5g's stored replies, and the result was compared with v6's own test:

- correct finds lost: 0 (v6 0);
- correct finds gained: the same 21 as v6;
- false positives removed: the same 246 as v6;
- false positives added: 4 (v6: 0 with both judges, 2 with either judge):
  - **trng fifo.we, r0 and r1:** one of v6's own judges already added it, so this is judge noise;
  - **debug_dtm tap_reg.dmi, r1 and r2:** the probes show this comes from how the test presents changes, not from a
    change of meaning. Shown the same way, v6's own text gets the same promotion from 1 of 2 judges. The real v6 runs
    list tap_reg.dmi as primary in r0 and r2. See CONDENSE_V6.md.

This test is an upper bound on rule-following. v6's own test predicted precision 0.70-0.77; the real run gave
0.60-0.64.

## What it breaks

- Nothing in the reply format: chain.py, the scorers and the views read it as they read v6.
- Checks keyed on v6's exact wording (core sentences, rule texts) must use this version's wording.

## Readings and falsifiers (set before the run; compare with v6 r0-r2 only, never pooled)

The claim is that v6abc makes the same decisions as v6. v6's three runs gave precision 0.601 / 0.619 / 0.642 and
recall (of 109) 0.789 / 0.761 / 0.789 (re-derived 2026-10-13 with compare_v6.py's scorer).

1. **Recall:** 2 or more v6abc runs below 0.761, v6's lowest run, **falsifies** the claim.
2. **Precision:** 2 or more v6abc runs below 0.601, v6's lowest run, **falsifies** the claim.
3. **Element losses:** a reference element found in all 3 v6 runs but in at most 1 v6abc run is a loss.
   - To find the cause, run v6a, v6b or v6c: each holds one track.
   - Then restore the v6 wording of the sentence that caused the loss.
4. **Format:** zero slips, including missing walks (seen in v6 r2 bus).

## How to run (paid; the user runs it)

1. Restart the notebook kernel. Run cell 1 (`INPUT_VERSION = "v1"`), then cell 9.
   - Cell 9 already runs v6a, v6b, v6c and v6abc, 3 runs each (set up 2026-10-13).
   - It prints a preview first and sends nothing until `RUN_MANY = True`.
2. Read the results with
   `python analysis/two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2/compare_condensed.py`. It also checks that every
   module of every run has an assets file and that nothing is pending.

**Cost estimate:** about USD 2.1 for 3 runs. v6's 3 runs cost USD 2.08, from its stored usage (Phase 1 0.81,
Phase 2 1.28). This version's prompts are about 5% shorter.
