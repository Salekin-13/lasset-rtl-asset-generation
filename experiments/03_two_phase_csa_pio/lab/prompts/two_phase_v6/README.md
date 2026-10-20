# two_phase_v6: v5g + paired Phase 1 / Phase 2 rules from the v5g failure analysis (built 2026-10-13, not run)

## What it is

- **Base:** v5g.
- **The user's request (2026-10-13).** From the v5g three-run failure analysis:
  - find the causes of the consistent false positives and misses;
  - write rules for both phases so that the whole prompt stays consistent;
  - remove or restrict the extra concepts that cause false positives, without losing correct finds;
  - for the elements v5g could not find, draft narrow rules that make Phase 1 emit the missed concepts, and instruct
    Phase 2 to read the diagrams carefully.
- **Built by:** `analysis/prompt_builds/make_v6.py`, from `analysis/two_phase_v5g__gpt-5.6-luna__high__r0-r2/rules/v6_candidate/`.
- **Checks passed:**
  - the system shas match the boundary-tested candidate: Phase 1 `e815598c3dda`, Phase 2 `773926fea6fb`;
  - the reply format (OUTPUT sections) and both user templates are byte-identical to v5g;
  - the project prompt checker is clean;
  - `chain.new_format` reads the format, and `format_tests.py` passes.
- **Words:**

  | File | v5g | v6 |
  |---|---|---|
  | phase1.md | 2,849 | 6,200 |
  | phase2.md | 4,606 | 7,863 |
  | common.md | 4,420 | 4,265 |

  common.md shrinks because two of its bars (U1 and U6) move into paired rules in the two phase files.
- **Both shas change**, so this version needs full runs: Phase 1 and Phase 2.

## How the rules were made

All the agents involved were Claude agents. The files are in `analysis/two_phase_v5g__gpt-5.6-luna__high__r0-r2/`.

1. **The failure analysis** to the user's specification: `THREE_RUN_FAILURES.md` (wf_6a4e92b2-c2b). The change
   attribution against v5f: `V5G_RESULTS.md` (wf_91fa05de-dcc).
2. **Code-computed evidence** (`rules/rules_prep.py`, self-tested):
   - 50 extra-concept groups. 48 carry no correct find, and they hold 161 of v5g's 352 false-positive rows. No correct
     find depends only on an extra concept.
   - 61 misses: 22 labelled secondary, 16 with no concept holding them, 12 held but never named, 11 from the format slip.
3. **The rules workflow** wf_ce0308e1-806 (61 agents).
   - 15 items: 10 extra-concept clusters, the consistent false positives under matching concepts, and 4 recall items.
   - Each was drafted, checked by two skeptics (correct-find risk; consistency and constraints) and revised.
   - An integration check followed: 19 overlapping edits re-anchored, merges, one Phase 1 scoping sentence (FRAME-P1,
     word for word the same as Phase 2's FRAME), the order of application, and word counts.
   - Report: `rules/RULES_V6.md`. Exact texts: `rules/RULES_V6_APPENDIX.md`.
4. **The integrated text** was rebuilt by re-running the integrator's own build code (`rules/make_candidate.py`). Its
   shas matched the integrator's report.
5. **Blind boundary test** (wf_b1d6d6cc-c10, 30 judges, scored by `boundary/score_v6.py`; self-tests passed).
   - Two judges per module applied the new texts to v5g's stored concepts (blind concept views) and Phase 2 rows (blind
     row views).
   - **0 correct finds lost** by either judge.
   - 21 correct finds gained.
   - 246 false positives removed; 0 added (both judges) or 2 added (either judge).

## The rules (ids as in RULES_V6.md)

- **Restrictions against extra concepts.** Each restriction has one core sentence, word for word the same in phase1.md
  and phase2.md. Phase 1: not a piece / keep no concept / do not cite as held lines. Phase 2: never primary, can be a
  secondary.
  - CX7.U1b and CX7.U4b: interrupt-enable bits, flow-control and clock-shape settings.
  - CX3.U6p: CPU wrapper control state on internal hand-off records.
  - CX9-U and CX9-S1: status bits that only report other state.
  - CX2.U3b: sequencing state, replacing U3 "Serial engines"; it carries the merged NC.STEP.
  - CX5.1: control-bus qualifiers.
  - CX6.U13: payload only passed on.
  - CX4.TF1: one-bit transaction flags; it rewrites U10 and I11.
  - CX1-ACF: access command fields.
  - CX10.1 and CX10.2: registered output stages.
  - CX8.K1s: per-sub-unit CSR state.
  - Label: **user decision, reference convention, to raise precision**, under the user's decision of 2026-10-12.
    CX8.K1s has a split label.
- **Restrictions against false positives under matching concepts:** P11.1 to P11.6.
  - Basis: LAsset p2 / SAIF p2, through ASSET_DEFINITION.md lines 58-59 ("pure carriers are secondary").
- **Recall:**
  - NC.K2S sharpens the Hand-offs rule.
  - R-M5-modeselect is a mode-select pin of a test access port, with IEEE 1149.1 as basis; it carries the merged
    NC.TMS.
  - W1 is the Phase 2 diagram-walk completeness instruction (steps 1 and 3).
  - LS1 and LS2 are Phase 2 label rules.
- **Held for the user's decision:** NC.SCR, NC.FIFOb and NC.K2SW. Their drafters found no published basis and set a
  default of holding them back.
- **Not in this change:** W2, meant for a separate arm.

## Blind estimate (an upper bound; read with care)

| Run | Precision v5g -> v6 | Recall (of 109) v5g -> v6 |
|---|---|---|
| r0 | 0.477 -> 0.767 | 0.752 -> 0.817 |
| r1 | 0.401 -> 0.708 | 0.817 -> 0.890 |
| r2 | 0.424 -> 0.721 | 0.872 -> 0.927 |

These figures are from both judges. The test assumes the model follows every rule, and that is the weak point:

- v5's blind test predicted about twice the false-positive removal its run delivered.
- v5g's predicted precision of about 0.50-0.55; the real run gave 0.43, because Phase 2-only bars were ignored.

v6 pairs each bar with a Phase 1 rule, since targets disappeared mainly when Phase 1 did not build the concept. Still,
expect the real gain to be well below this estimate.

## What it breaks

- **Prompt length.** Phase 1 more than doubles, and the Phase 2 step-4 paragraph goes from 2,315 to 5,379 words. A
  longer Phase 1 was linked to recall losses in v5. This is the main risk.
- **Attribution.** About 24 rules ship at once, so a change cannot be credited to one rule. Read each rule's targets
  instead (RULES_V6_APPENDIX.md).
- **Old presence checks.** Checks keyed on old texts (check_v5.py, the v4a phrase check) will report the rewritten
  rules as missing: U1, U3, U6, U10, I2, I11, I13, I15, K1, R5's tail and U7's last sentence.

## Readings and falsifiers (set before the run; compare with v5g r0-r2 and v5f r0-r5, never pooled)

1. **Precision:** at least 2 of 3 v6 runs above 0.500, the highest of v5f's six runs and v5g's three. **Falsified if
   fewer.**
2. **Recall (of 109):** 2 or more v6 runs below 0.780, the lowest v5f run, **falsifies** the claim that length and
   rules do not cost recall. Then split the build: the P-track restrictions first, the recall rules second.
3. **Element losses:** any reference element found in 5 or more of v5f's 6 runs and 2 or more of v5g's 3, but in at
   most 1 v6 run, is a loss. Trace it to a rule; narrow or drop that rule.
4. **Compliance per rule:** the share of each rule's targets that are still primary.
5. **Phase 1:** the extra concepts per run (judged) should fall from v5g's 35 / 32 / 39. Reference-concept recall
   should not fall below v5g's 0.909 / 0.870 / 0.961.
6. **Format:** zero slips, including the nesting slip seen once in v5g r0.

## How to run (paid; the user runs it)

1. Restart the notebook kernel.
2. In cell 1, set `INPUT_VERSION = "v1"`. In cell 9, set `JOBS = [("two_phase_v6", r) for r in (0, 1, 2)]`.
3. Before analysing, check that every module of every run has an assets file and that `_pending/` is empty. v5g's run
   ended early once.

**Cost estimate:** about USD 2.31 for 3 runs. That is v5g's measured USD 2.23 plus the larger system prompts at the full
input price.
