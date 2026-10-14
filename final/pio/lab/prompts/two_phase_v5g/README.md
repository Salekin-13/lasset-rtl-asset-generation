# two_phase_v5g: v5f + Phase 1 / Phase 2 consistency fix in phase2.md (built 2026-10-13, not run)

## What it is

- **Change.** v5f, with phase2.md changed so that Phase 2 follows the same rules as Phase 1. common.md, phase1.md and
  both user templates are byte-identical to v5f. So the Phase 1 system sha stays `f05279744fdc`, and v5f's stored
  Phase 1 replies are reused.
- **Phase 2 system sha:** v5f `453c149c76b7` -> v5g `57b22998b41f`.
- **Words:** phase2.md 2,278 -> 4,606 (+2,328). The uncompressed version would add 2,903
  (`analysis/two_phase_v5f__.../consistency/phase2_long.md`).
- **Build:** `analysis/prompt_builds/make_v5g.py`. Checks passed: the other files are byte-identical; the Phase 1 sha
  is unchanged; undoing the inserts gives v5f; the project prompt checker passes; the runner reads the format
  (`chain.new_format`).
- **Why (user, 2026-10-13):** "find if there are any inconsistencies in rules between phase 1 & 2, if there are, fix
  phase 2". This includes the user's earlier choice to copy five Phase 1-only restrictions into Phase 2 (U2, U3, U5, R2b,
  Working values).

## How the text was made (all Claude agents; files in analysis/two_phase_v5f__gpt-5.6-luna__high__r0-r2/consistency/)

1. **Audit** (wf_5d7fb7b2-d73, 103 agents).
   - Five finders, each with a different lens: Phase 1-only restrictions (two parts), definitions, own pieces with no
     primary path, and cross-phase promises with data.
   - The findings were merged into 25 (I1-I25).
   - Three skeptics checked each finding: the text, the data, and whether phase2.md can fix it.
   - Of the 25, 23 were kept: at most 1 of 3 skeptics refuted them.
   - Drafts were written for the 21 fixable findings, then an integration check ran across them.
   - Report: `AUDIT_FINDINGS.md`.
2. **Integration** (`make_long.py`): the resolutions of the integration check.
   - I16 was dropped, because it duplicates I1-I7.
   - I8 was reordered so that I10 follows it, and I11 covers both lock-bit examples.
   - FRAME was added: one rule's "judged as usual" items do not protect an element from another rule's bar.
   - I26 was added: Phase 2's mapping for the three stale "the reason" pointers in common.md (lines 62, 93, 121). The
     v5f format change left those pointers behind.
3. **Compression** (wf_0b540b62-d24, 12 agents).
   - Two strategies were tried. The chosen one tightens each rule and adds 2,328 words. The shared-frame strategy added
     2,191 words but widened bars that already exist in v5f.
   - Two clause checkers, after two repair rounds, found the result "equivalent" to the long text.
   - Inserted texts: `inserts_compressed.md`.
4. **Blind boundary test** (wf_859ba8d0-07c, 30 agents, scored by `boundary/score_boundary.py`).
   - Two blind judges per module applied the new sentences to every stored v5f Phase 2 row.
   - The scorer's self-test reproduces v5f's real scores.

## What changes (draft ids from AUDIT_FINDINGS.md)

| Group | Drafts | Label |
|---|---|---|
| Copies of Phase 1-only restrictions | I1 (U2 FIFO port buffers), I2 (U3 serial engines), I3 (U5 cached copies), I4 (R2b pacing pulses), I5 (Working values: partial results), I6 (Working values: synchronizer stages), I7 (step 3: started flags), I8 (R7b reset chains), I9 (U4 clock-line shape), I10 (U8 refused writes), I11 (U10 arbitration bookkeeping), I12 (U7 operation selectors), I13 (R5 records wired into another IP), I15 (K1 read words passed in) | Each copy keeps its Phase 1 rule's label: published basis for R rules, user decision for U rules |
| Alignments | I14 (a routing decision with no element of its own), I19 (a serial boundary port carries its value whole; decoded select outputs), I25 (ROM read data), I20 (a walk with no primary), I22 (missing "Objectives At Risk"; undermined expected behavior), I26 ("the reason" pointers), FRAME (scoping) | Alignment with common.md or phase1.md |

- **Refuted, not applied:**
  - I17 (concepts with no legal primary: 2 of 3 skeptics refuted it);
  - I18 (anchor rule vs R1: 3 of 3 refuted it).
- **Not fixable in Phase 2:** I23 and I24. I23 is a tension inside Phase 1 (step 3's timing clause vs the "judged as
  usual" start pulses). I24 is a compliance slip.
- **No edit:** I21 (dead clock/reset walk text).

## Blind estimate (upper bound)

Applied to v5f's stored rows (r0 / r1 / r2):

| Measure | v5f now | v5g, both judges | v5g, either judge |
|---|---|---|---|
| Precision | 0.442 / 0.397 / 0.418 | 0.552 / 0.506 / 0.503 | 0.569 / 0.532 / 0.516 |
| Recall (of 109) | 0.835 / 0.780 / 0.844 | 0.872 / 0.835 / 0.862 | 0.872 / 0.835 / 0.862 |

- Correct finds lost: 0, by either judge.
- Correct finds gained: 12 (I19 10, I25 2).
- False positives removed: 113 (both judges) to 132 (either judge). None added.
- **Read this as an upper bound.** v5's blind test predicted about twice the false-positive removal that its run
  delivered (V5_RESULTS.md).
- **FRAME's compressed wording reaches further.** Its sentence "each bar in this step ... holds even when CONCEPTS
  names the element ... or lists it under 'Enters Through' or 'Leaves Through'" also covers bars that v5f already had,
  such as R1 for bus record ports. Most of the false positives credited to FRAME (68 to 87) are such v5f lapses. So
  part of the estimate is better compliance, not a new rule.

## What it breaks

- **Prompt length.** phase2.md doubles. A longer Phase 1 was linked to recall losses in v5. This is the main risk.
- **Comparability.** Compare only within the Phase 2-only design below, never with v5f's full runs pooled.

## How to run (paid calls are the user's)

1. `python analysis/prompt_builds/prepare_phase2_only.py --apply` copies v5f's r0-r2 Phase 1 replies:
   - into v5g r0-r2 (the arm);
   - into v5f r3-r5 (the control).

   A dry run passed: 90 files, every sha matches.
2. Restart the notebook kernel. Set `JOBS = [("two_phase_v5g", r) for r in (0, 1, 2)] + [("two_phase_v5f", r) for r
   in (3, 4, 5)]`. Phase 1 is not asked again; only 90 Phase 2 calls are paid.
3. **Cost estimate:** v5f's Phase 2 cost USD 0.45-0.48 per run (measured), so about USD 3 for the 6 runs.

## Readings and falsifiers (set before the run)

Compare each arm run with the control run on the same Phase 1 reply: r0 with r3, r1 with r4, r2 with r5.

1. **Precision** of the arm above the control's in at least 2 of 3 pairs.
   - **Falsified (precision)** if not.
2. **Recall (of 109)** of the arm not below the control's in 2 or more pairs.
   - **Falsified (length or rules cost recall)** if it is. Then split the build: the five decided copies (I1-I6) plus
     FRAME first, the rest second.
3. **Element losses:** any reference element found in all 3 control runs but in 1 or fewer arm runs is a loss. Trace it
   to a draft and narrow or drop that draft.
4. **Target false positives per draft** (the lists in AUDIT_FINDINGS.md): count how many are still primary. This shows
   compliance per copy.
5. **Format:** asset rows and points that lose their name stay at 0 of 45 replies.
