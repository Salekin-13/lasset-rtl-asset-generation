# two_phase_v6b: v6 with phase2.md condensed (built 2026-10-13, not run)

## What it is

- **Base:** two_phase_v6. Only phase2.md changes. The core sentences (the 35 sentences that occur word for word in
  both phase files) stay exactly as in v6, so the two phases still match.
- **The user's request (2026-10-13):** condense Phase 2 down in the same way as Phase 1 (v6a): the same instruction
  meanings with fewer words, less vague words, shorter and specific sentences, and the core sentences kept the same.
  Condense as much as possible without lowering the model's performance.
- **Built by:** `analysis/prompt_builds/condense_v6/` (report: `CONDENSE_V6.md`), the same pipeline as v6a.
- **Checks passed:**
  - 10 of 12 phase2 pieces were judged equivalent by both clause checkers and passed the code checks;
  - p2_02 and p2_08 were not judged equivalent and keep v6's text;
  - OUTPUT sections, common.md, phase1.md and both user templates are byte-identical to v6;
  - each core sentence occurs once in each phase file;
  - the project prompt checker is clean, and `chain.new_format` reads the format;
  - a read-through (wf_783a745d-545) found no broken cross-references or joins.
- **Words:** phase2.md 7,863 -> 7,545 (-4.0%). phase1.md and common.md are unchanged.
- **Shas:** Phase 1 `e815598c3dda` (v6's), Phase 2 `68d9782d1999` (new).

## Phase 2-only test

v6b's Phase 1 system and user messages are exactly v6's. So v6's stored Phase 1 replies can be reused, and only the
Phase 2 calls are new.

- **Arm:** v6b r0-r2 use v6 r0-r2's Phase 1 replies. `analysis/prompt_builds/prepare_v6b_phase2_only.py` copies them
  after checking each record's shas against today's v6b messages. **Copied on 2026-10-13:** 45 files, all checks
  pass, each file byte-identical to v6's.
- **Control:** v6's own Phase 2 on the same Phase 1 replies (v6 r0-r2). The comparison is paired run by run, so no extra
  control run is needed.
- **Limit:** Phase 2's own run-to-run spread on a fixed Phase 1 has never been measured (v5f r3-r5 were full runs, not
  Phase 2 reruns). So a difference of a few correct finds between v6b and v6 in one run cannot by itself be called an
  effect of condensing.

## What it breaks

- Nothing in the reply format: chain.py, the scorers and the views read it as they read v6.
- Old presence checks keyed on v6's Phase 2 wording will report reworded sentences as missing.

## Readings and falsifiers (set before the run; compare with v6 r0-r2 only, never pooled)

The claim is that v6b makes the same Phase 2 decisions as v6 on the same concepts. v6's three runs gave precision
0.601 / 0.619 / 0.642 and recall (of 109) 0.789 / 0.761 / 0.789 (re-derived 2026-10-13 from compare_v6.py).

1. **Recall:** 2 or more v6b runs below 0.761, v6's lowest run, **falsifies** the claim.
2. **Precision:** 2 or more v6b runs below 0.601, v6's lowest run, **falsifies** the claim.
3. **Paired element changes:** per run, list the reference elements found by v6 but not by v6b on the same Phase 1
   reply. An element lost in 2 or more runs is traced to a condensed sentence, and that sentence's v6 wording is
   restored.
4. **Format:** zero slips, including missing walks (seen in v6 r2 bus).

## How to run (paid; the user runs it)

1. **Done on 2026-10-13:** the dry run printed `checks: PASS (45 files)`, then `--apply` copied the 45 Phase 1 replies
   (`python analysis/prompt_builds/prepare_v6b_phase2_only.py [--apply]`).
2. Restart the notebook kernel. Run cell 1 (`INPUT_VERSION = "v1"`), then cell 9.
   - Cell 9 already runs v6a, v6b, v6c and v6abc, 3 runs each.
   - It first prints a preview; v6b must show 15 Phase 1 replies stored in each run.
   - It sends nothing until `RUN_MANY = True`.
   - The runner reuses the copied Phase 1 replies and calls only Phase 2 for v6b.
3. Read the results with
   `python analysis/two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2/compare_condensed.py`. It also checks that every
   module of every run has an assets file and that nothing is pending.

**Cost estimate:** about USD 1.3 for 3 runs. v6's Phase 2 calls cost USD 1.28 over 3 runs, from its stored usage.
v6b's Phase 2 prompt is 4% shorter.
