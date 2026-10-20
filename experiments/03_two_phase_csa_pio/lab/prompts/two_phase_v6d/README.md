# two_phase_v6d: v6abc with its traced culprit put back to v6's wording: the FINAL condensed prompt (2026-10-13)

**Status: final condensed prompt (user decision 2026-10-13), and the base of the final prompt two_phase_v7.** Ran 3 times.

| | Precision (correct ÷ listed) | Recall (correct ÷ 109 per run) |
|---|---|---|
| v6d | .601 / .641 / .610; pooled 253/410 = 0.617 | .789 / .771 / .761; pooled 253/327 = 0.774 |
| v6 | pooled 255/411 = 0.620 | pooled 255/327 = 0.780 |

- Neither README reading fired.
- Level with v6: Phase 2's own spread is 0-5 correct finds per run, and a module-level sign test gives p 1.00.
- Recall is above v6abc's (0.722 over 6 Phase 2 draws), with precision level.
- See SPREAD_RESULTS.md in analysis/two_phase_v6abc_phase2_spread__gpt-5.6-luna__high__r3-r5/. The text below was
  written before the run.

## What it is

- **The user's request (2026-10-13):** trace the elements the condensed versions lost, and make the fixed prompt v6d.
  This follows the rule each condensed README set before the run: trace a loss to a condensed sentence and restore that
  sentence's v6 wording.
- **Trace** (wf_de176bc0-f7a; analysis/prompt_builds/condense_v6/trace/, TRACE_V6DE.md):
  - 10 elements were traced: the README losses, plus every element found in 2 or more fewer runs than in v6.
  - One tracer per element named candidate units, and one skeptic per element tried to refute each.
  - 15 candidate (element, unit) pairs over 12 distinct units were named, and 14 were refuted. Only **p2_05.0** survived,
    at low confidence. It is the start of Phase 2's
    step 4 and is linked to spi clkgen_en_o in v6b.
- **Built by** `trace/make_v6de.py` (checks passed: prompt checker, new_format, OUTPUT sections identical to v6, core
  sentences once per file, same line count as v6, restored wording present).
- **Words:** phase1.md 5,866 (v6abc's), phase2.md 7,451 (v6abc 7,408, v6 7,863).
- **Shas:** Phase 1 `4a1d22d55f30` = v6abc's; Phase 2 `055cf2301409`.

## Run design: Phase 2 only, paired with v6abc

v6d's Phase 1 is v6abc's byte for byte. So v6abc's stored Phase 1 replies are copied in
(`prepare_phase1_copy.py two_phase_v6d --from=two_phase_v6abc`, done 2026-10-13: 45 files, byte-identical). Only Phase 2
is sent. The comparison is v6d rX against v6abc rX, on the same concepts, and the only difference is p2_05.0.

## What to expect (reasoning, set before the run)

The trace found no unit-level cause for most losses. The recall drop of v6abc is real in total: an element sign test
against v6 gives p < 0.001, with 29 elements found less often and 7 more often. But it is spread over many elements. So
restoring one unit is **not** expected to recover v6's recall. v6d tests that expectation cheaply.

## Readings (set before the run)

1. **Paired, against v6abc:**
   - spi clkgen_en_o primary in 2 or more runs, where v6abc had it in 3 of 3 and v6b in 1 of 3, supports p2_05.0 as
     its cause;
   - recall up by 3 or more correct finds per run in 2 or more runs would mean more than that one element changed.
2. **Against v6:** the same readings as v6abc. Recall below 0.761 in 2 or more runs means v6d does not fix the loss.
3. **Format:** zero slips (v6abc r0 had 7 missing walks).

## How to run

Notebook cell 9 runs v6d and v6e, 3 runs each, and sends nothing until `RUN_MANY = True`. Restart the kernel and run
cell 1 first. Read the results with
`python analysis/two_phase_v6_condensed__gpt-5.6-luna__high__r0-r2/compare_condensed.py`.

**Cost:** about USD 1.3, Phase 2 only. v6's Phase 2 calls cost USD 1.28 for 3 runs.
