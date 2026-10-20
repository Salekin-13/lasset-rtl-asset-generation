# two_phase_v10: v9 with its 17 hardest rules rewritten (built 2026-10-16; NOT run)

**Status:** built and checked; not run. Nothing below is a measurement of v10 on the model.

Built by `analysis/prompt_builds/v10/make_v10.py --write` (user, 2026-10-16: "Add the E1 status-bits fix to
current_rules.json, keep dm_ctrl.busy on the v10 watch list, then build v10 with make_v10.py --write").
System prompt sha12: phase 1 `9385aa458632`, phase 2 `a4719593614e` (v9: `a91834bb2082` / `0d77634a9d2b`).
Words: phase1.md 7,061 -> 7,624 (+563); phase2.md 8,553 -> 9,010 (+457); common.md unchanged (4,265).

## What changed from v9

Only the 17 rules the rule-alone tests found hard to read, plus one shared sentence. `common.md`, both user templates,
both OUTPUT sections and every other line and sentence are byte-identical to v9 (the builder checks this).

- **Each of the 17 rules is now a block:** Scope, Criteria, Exceptions (where any are left), Outcome, Evidence.
  - **12 rules** take the v10 rewrite (`prompt_builds/v10/dossiers/G*_final.json`): Pacing pulses, Forwarded
    transactions, Second copies, Bus handshake copies, Working values, Hand-offs, Port buffers, Serial shift registers,
    Operation selectors, Access command fields, Per-region checks, Processor context fields.
  - **4 rules** take the "facts-first" wording (`prompt_builds/v10f/`): Sequencing state and Port options (A, B),
    Clocks and resets (C), Slices (D).
  - **Buffer and engine status bits** takes the E1 fix (`prompt_builds/v10/e1/`): its scope is "a status bit in the data a
    bus read returns", and its sequencing-state gloss uses Sequencing state's own words.
  - The list of which file each rule comes from is `prompt_builds/v10/current_rules.json`.
- **One shared "Reading a rule" sentence** (Phase 1 after "- Precedence.", Phase 2 before the first rule block):
  "Check its scope, then each criterion, then each exception it lists, in that order, against the RTL; where a criterion
  says "only", "every" or "one element", check every assignment or use, not one. Its outcome follows only for an element
  in scope that meets every criterion (one, where marked "any of") and that no listed exception covers."
- **The reply format is unchanged** (decision G3, 2026-10-16: no per-signal facts in the replies).

## How each piece was tested (rule alone; clarity, not precision or recall)

| What | Test | Report |
|---|---|---|
| The 17 rewrites vs v9 | luna, 41 modules | V10R_RETEST_RESULTS.md |
| Facts-first wordings; Slices, Clocks rounds | luna, 41 modules | V10F_RESULTS.md |
| Clarity on 6 modules no fix was made from | luna | CLARITY_UNSEEN_RESULTS.md |
| The 4 adopted wordings without the facts reply format (G3) | luna, 41 modules | V10F_RESULTS.md "G3 test" |
| The shared sentence (E2/E3) | Claude, 4 modules, batched | E3_RESULTS.md |
| The status-bits fix (E1) | Claude, 7 modules, one rule per agent | E1_RESULTS.md |

All reports are in `analysis/rule_isolation_v9/`. Placement differs slightly from the tests: there, the Phase 2 shared
sentence ended the step-4 line; here it stands before the first rule block.

## Readings set before the run (2026-10-16; cuts chosen here, stated as such)

Measure: `analysis/heldout_versions__gpt-5.6-luna__high__r0-r2/compare_versions.py two_phase_v10` (exact scorer,
pooled over r0-r2), against v9's stored r0-r2 from the same script. Groups: **tuning_v2** = the 15 tuning modules plus the
12 held-out modules that caused v7's drop (`splits/tuning_v2.json`; the script reports them as "tuning" and "held-out:
the 12", to be summed, checked equal to the split on 2026-10-16); **heldout_v2** = the other 14 ("held-out: other 14").
*Precision* = of the signals v10 lists as primary, the share the reference lists. *Recall* = of the reference's
signals, the share v10 lists.

- **V1 (primary, tuning_v2):** pooled precision and pooled recall each not lower than v9's by more than 0.02 (cut chosen
  here, not derived from a measured spread). PASS -> v10 replaces v9 as the working version. The rewrite aimed at clearer rules, not at new
  targets, so it should cost neither.
- **V2 (read, the point of the rewrite):** run-to-run stability on tuning_v2: the share of primary listings that appear
  in all 3 runs, v10 vs v9. Expected to rise.
- **V3 (heldout_v2, "does not hurt" only):** precision and recall each not lower than v9's by more than 0.03. These
  modules supplied cases for some fixes, so a pass here is not proof of generalisation.
- **V4 (watch list, decision G3):** the 17 reference signals that one run of Sequencing state barred in the G3 test:
  wdt cnt, cnt_timeout, reset_wdt; pwm cfg_cdiv, cfg_en, cfg_prsc, clkgen_en_o, clkgen_i, pwm_o, we_i; bus keeper.cnt,
  keeper.err, keeper.halt; **debug_dm dm_ctrl.busy**; cpu_lsu mar; cpu_cp_shifter shifter.cnt, shifter.done_ff.
  Read: (signal, run) pairs listed primary, v10 vs v9. A drop of more than 2 -> the next step is a facts step for
  Sequencing state alone (the G3 fallback).
- **V5 (watch, the E1 fix):** debug_dm dm_ctrl.busy is now barred by Buffer and engine status bits in both of its
  wordings (E1_RESULTS.md). Read its primary runs in v10 vs v9 (it is in V4 too). Also read that the FIFO-flag and busy
  bits the rule bars (uart, spi, slink) are not listed primary in more v10 runs than v9 runs.
- **V6 (read, cost):** output tokens per call, v10 vs v9 (v10's system prompts are longer: phase 1 64,696 -> 68,383
  characters, +5.7%; phase 2 73,886 -> 76,912, +4.1%).

## Running it

On OpenAI (luna, high), all 41 modules: v9's full runs cost USD 1.95-1.96 each (82 calls, measured from its stored
usage), so 3 runs of v10 should cost about USD 6. A run on Claude agents instead would need about 82 large agent calls
per run and could not be compared with v9's luna runs.
