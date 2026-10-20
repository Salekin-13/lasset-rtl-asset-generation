# two_phase_v6a: v6 with phase1.md condensed (built 2026-10-13, not run)

## What it is

- **Base:** two_phase_v6. Only phase1.md changes. The core sentences (the 35 sentences that occur word for word in
  both phase files) stay exactly as in v6, so the two phases still match.
- **The user's request (2026-10-13):** condense Phase 1 down; keep the same instruction meanings with fewer words; use
  less vague words and shorter, specific sentences; keep the core sentences between Phase 1 and Phase 2 the same.
  Condense as much as possible without lowering the model's performance.
- **Built by:** `analysis/prompt_builds/condense_v6/` (report: `CONDENSE_V6.md`):
  - make_condense_inputs.py split the text;
  - the workflow wf_965ed976-a65 condensed each piece and had two clause checkers compare it with v6;
  - assemble_condensed.py assembled the text and ran the code checks.
- **Checks passed:**
  - all 9 phase1 pieces were judged equivalent by both clause checkers and passed the code checks;
  - OUTPUT sections, common.md, phase2.md and both user templates are byte-identical to v6;
  - each core sentence occurs once in each phase file;
  - the project prompt checker is clean, and `chain.new_format` reads the format;
  - a read-through (wf_783a745d-545) found no broken cross-references or joins.
- **Words:** phase1.md 6,200 -> 6,003 (-3.2%). phase2.md and common.md are unchanged.
- **Shas:** Phase 1 `acc653b532bb` (new), Phase 2 `773926fea6fb` (v6's). Phase 1 changes, and Phase 2 reads Phase 1's
  concepts, so this version needs full runs.

## What it breaks

- Nothing in the reply format: chain.py, the scorers and the views read it as they read v6.
- Old presence checks keyed on v6's Phase 1 wording will report reworded sentences as missing.

## Readings and falsifiers (set before the run; compare with v6 r0-r2 only, never pooled)

The claim is that v6a makes the same decisions as v6. v6's three runs gave precision 0.601 / 0.619 / 0.642 and recall
(of 109) 0.789 / 0.761 / 0.789 (re-derived 2026-10-13 from compare_v6.py).

1. **Recall:** 2 or more v6a runs below 0.761, v6's lowest run, **falsifies** the claim.
2. **Precision:** 2 or more v6a runs below 0.601, v6's lowest run, **falsifies** the claim.
3. **Element losses:** a reference element found in all 3 v6 runs but in at most 1 v6a run is a loss. Trace it to a
   condensed sentence and restore that sentence's v6 wording.
4. **Phase 1:** the concept count per run and the held lines should stay near v6's.
5. **Format:** zero slips.

## How to run (paid; the user runs it)

1. Restart the notebook kernel. Run cell 1 (`INPUT_VERSION = "v1"`), then cell 9.
   - Cell 9 already runs v6a, v6b, v6c and v6abc, 3 runs each (set up 2026-10-13).
   - It prints a preview first and sends nothing until `RUN_MANY = True`.
2. Read the results with
   `python analysis/two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2/compare_condensed.py`. It also checks that every
   module of every run has an assets file and that nothing is pending.

**Cost estimate:** about USD 2.1 for 3 runs. v6's 3 runs cost USD 2.08, from its stored usage (Phase 1 0.81,
Phase 2 1.28). v6a's Phase 1 prompt is 3% shorter.
