# two_phase_v5f: v5 with new reply formats (built 2026-10-13, not run)

**Runner support (2026-10-13).** `chain.py` now reads this format.

- `new_format()` detects it from the OUTPUT section.
- `from_format_phase1()` and `from_format_phase2()` check each reply against the format. The problems they report
  start with "format:" or "consistency:". The problems are reported, never repaired. They do not trigger a re-ask.
- The same functions then store the reply in v5's keys under "reply". "raw" keeps the reply as written.
- Phase 2 receives Phase 1's "Conceptual Assets" list as written.
- The checks, the converter and the analysis scripts work unchanged.
- Tests (no model call), all passing on 2026-10-13:
  - `python final/pio/lab/format_tests.py`: 41 checks. These include a round trip of all 90 stored v5 replies (same
    mapped fields, same checks, same scored assets) and planted format errors.
  - `chain.py selftest` and `chain_tests.py`: unchanged results for v1 to v5.
- **Restart the notebook kernel before running.** A kernel that still holds the old `chain` module would treat every
  Phase 1 reply as a schema failure and ask it twice.

## What it is

- **Same rules as v5.** No rule text changed. Only the two OUTPUT sections changed, plus the sentences that name reply
  fields, and one sentence that asks for the format to be followed strictly.
- **Built by** `analysis/prompt_builds/make_v5f.py`. Every edit is an exact replacement that must match once.
- **Checks passed** (2026-10-13):
  - the project prompt checker (no corpus names, no banned words, no numeric hints);
  - every edit present;
  - undoing the edits gives v5 byte for byte, with v5's line endings;
  - no old reply-field name left in quotes;
  - every key name appears once per OUTPUT template (Phase 1: 25 keys, Phase 2: 33 keys).
- **Inputs:** v1.
- **System prompt sha12** (common.md + phase file):
  - Phase 1: v5 95761173e1f5 -> v5f f05279744fdc.
  - Phase 2: v5 0c8ce85ae8d9 -> v5f 453c149c76b7.
- **Words:** common.md 4,368 -> 4,420; phase1.md 2,790 -> 2,849; phase2.md 2,134 -> 2,278.

## Why (user decision, 2026-10-13)

The user asked for reply formats that:
- a person can read easily, in the style of LAsset's own result file
  (`data/LAsset_initial_results/asset_list_neorv32_initial.json`);
- use each field name only once, so a value cannot slip into the wrong field;
- keep points, because points are needed to debug the prompt;
- keep primary and secondary as a label, not nested;
- are followed strictly.

Measured on stored replies (2026-10-13, scratchpad scripts `rederive_state.py`, `point_ids.py`,
`point_slip_shape.py`, `debug_fields.py`, `inventory.py`):

- **The format slip is in every version and in both Phase 2 lists.**
  - Asset rows without "element": 3 to 5 of 45 Phase 2 replies per version, v1 to v5.
  - Points with a concept id Phase 1 does not have: 1 to 7 of 45 replies per version. There are 88 such points over
    v1 to v5. In 86 of them, "concept id" holds the point's name; 85 have no "point".
  - The row's own name lands in the first key, "concept id". That key is repeated in every row. In v5f, rows sit under
    their walk and start with their own name; "Concept ID" appears once per walk.
- **Points carry debugging evidence.** v5 r0-r2 has 68 misses (of 109 per run). For 5 of them, a point is the furthest
  place the name appears. In v5, 572 of 1,609 points name no asset.
- **Free-text notes held facts that now get their own fields.**
  - 6 of the 68 misses appear only in Phase 2 notes. They become "Not Reported".
  - 21 of 327 v5 concepts had no primary. That case becomes "No Primary Reason".
  - Merges become "Merged Into". The cpu dbi_i loss came from a merged concept (V5_RESULTS.md).
- **The link field was followed in v5,** so it is kept as "Secondary To":
  - 0 of 744 primary rows had links;
  - 0 links lacked a direction;
  - 19 of 1,295 secondary rows had no link (the no-primary case).
- **Phase 1's format was healthy.** It had no bad ids. Its only missing key was "objectives": v2 2 rows, v4 5, v5 14
  (in 2 replies).

## What it breaks

- **Code that reads replies by key:**
  - in `chain.py`: `phase1_concepts`, `check_phase1`, `phase2_lists`, `check_phase2`, `to_assets`;
  - `build_pack3.py`, `parser_repair.py` and the judge views.
  - Fix: one adapter, used right after parsing.
- **Reuse of stored Phase 1 replies.** The Phase 1 system sha changes, so every Phase 1 call is new. This version cannot
  be part of a Phase 2-only test on v5's stored Phase 1 replies.
- **Comparability.** The model reads different OUTPUT sections and writes more per row: "Functionality" and
  "Justification" instead of one "reason", plus "Not Reported" entries. So a score change can come from the format
  alone. Compare it only with v5 r0-r2, never pooled with v5.

## Readings after the run (three runs, r0-r2; compare with v5 r0-r2)

| Reading | v5 baseline (measured 2026-10-13) |
|---|---|
| Phase 2 replies with an asset row lacking "Asset RTL" | rows lacking "element" in 4 of 45 replies |
| Phase 2 replies with a point lacking "Point", or in a walk whose "Concept ID" Phase 1 lacks | 5 of 45 |
| Phase 1 replies with a conceptual asset lacking a key | 2 of 45 (14 rows lacking "objectives") |
| Precision (exact) | 0.370 / 0.375 / 0.407 |
| Recall (exact, of 109) | 0.835 / 0.743 / 0.798 |
| Walks with no primary and an empty "No Primary Reason" | new field |
| Elements under both "Assets" and "Not Reported" in one walk | new field |

**Falsified if** either of these happens:
- Format: replies with nameless asset rows are not fewer than v5's 3 to 5 of 45. Then the new order did not prevent
  the slip.
- Accuracy: either of these happens:
  - in 2 or more runs, precision or recall falls below v5's lowest run;
  - 3 or more elements found in all three v5 runs are found in at most one v5f run.

  Then the format change costs accuracy.

**Cost estimate:** v5's three runs used USD 0.81 (Phase 1) + 1.29 (Phase 2) = 2.10 (measured from the stored usage).
v5f writes a little more per row, so expect slightly more. This is an estimate.
