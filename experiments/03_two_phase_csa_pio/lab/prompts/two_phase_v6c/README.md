# two_phase_v6c: v6 with the shared core sentences condensed (built 2026-10-13, not run)

## What it is

- **Base:** two_phase_v6. Only the core sentences change: the 35 sentences of 6 or more words that occur word for word
  in both phase1.md and phase2.md (2,154 words). Each condensed core sentence is the same text in both files, so the
  phases still match. All other text in both files is v6's.
- **The user's request (2026-10-13):** condense the core sentences of both phases; keep the same instruction meanings
  with fewer words, less vague words and shorter, specific sentences. Condense as much as possible without lowering
  the model's performance.
- **Built by:** `analysis/prompt_builds/condense_v6/` (report: `CONDENSE_V6.md`), the same pipeline as v6a.
- **Checks passed:**
  - all 35 core sentences are used as condensed. S06 (Second copies) was briefly reverted and then restored, because a
    rerun showed it was not the cause of a boundary-test difference (REVERTED.txt);
  - OUTPUT sections, common.md and both user templates are byte-identical to v6;
  - each core sentence occurs once in each phase file;
  - the project prompt checker is clean, and `chain.new_format` reads the format;
  - a read-through (wf_783a745d-545) found no broken cross-references or joins.
- **Words:** phase1.md 6,200 -> 6,063 (-2.2%); phase2.md 7,863 -> 7,726 (-1.7%).
- **Shas:** Phase 1 `11eb4275bd9f`, Phase 2 `b4393ece6dcc`. Both change, so this version needs full runs.

## What it breaks

- Nothing in the reply format: chain.py, the scorers and the views read it as they read v6.
- The v6 core sentences are no longer present word for word. Checks keyed on them (for example, a search for a rule's
  core sentence in a reply's cited text) must use the v6c wording.

## Readings and falsifiers (set before the run; compare with v6 r0-r2 only, never pooled)

The claim is that v6c makes the same decisions as v6. v6's three runs gave precision 0.601 / 0.619 / 0.642 and recall
(of 109) 0.789 / 0.761 / 0.789 (re-derived 2026-10-13 from compare_v6.py).

1. **Recall:** 2 or more v6c runs below 0.761, v6's lowest run, **falsifies** the claim.
2. **Precision:** 2 or more v6c runs below 0.601, v6's lowest run, **falsifies** the claim.
3. **Element losses:** a reference element found in all 3 v6 runs but in at most 1 v6c run is a loss. Trace it to a
   condensed core sentence and restore that sentence's v6 wording.
4. **Format:** zero slips.

## How to run (paid; the user runs it)

1. Restart the notebook kernel. Run cell 1 (`INPUT_VERSION = "v1"`), then cell 9.
   - Cell 9 already runs v6a, v6b, v6c and v6abc, 3 runs each (set up 2026-10-13).
   - It prints a preview first and sends nothing until `RUN_MANY = True`.
2. Read the results with
   `python analysis/two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2/compare_condensed.py`. It also checks that every
   module of every run has an assets file and that nothing is pending.

**Cost estimate:** about USD 2.1 for 3 runs. v6's 3 runs cost USD 2.08, from its stored usage.
