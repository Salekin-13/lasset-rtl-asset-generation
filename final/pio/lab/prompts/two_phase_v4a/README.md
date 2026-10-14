# two_phase_v4a — v4's content in v2a's concise wording (2026-10-12, not run)

Base: `two_phase_v4`. **Same meaning as v4, fewer words.** It combines the three findings so far (Luna, three runs each):
concise wording kept v2's scores (v2a), specific Phase 1 language raised recall (v3), and the bus-record line raised
precision (v4). Compare v4a with v4 only (same model, effort, three runs).

| File | v4 words | v4a words | How |
|---|---|---|---|
| common.md | 4,926 | 4,109 | v2a's shortened common.md (meaning-checked against v2, 371 clauses) + v4's bus-record line word for word, after the 2.6 line on forwarding wires (`analysis/prompt_builds/make_v4a.py` asserts both) |
| phase1.md | 1,506 | 1,448 | v4's phase1.md shortened with the same meaning; the OUTPUT block is unchanged |
| phase2.md, phase1_user.md, phase2_user.md | | | byte-identical to v4 (and v2) |

System prompts (check_lab_prompt, clean): Phase 1 32,278 chars, sha12 `b13686bbccbf` (v4: 36,437, `82e24b9513ae`);
Phase 2 35,937 chars, sha12 `1c69fe88de91` (v4: 39,837, `ca98760b47a5`). `build_check.py two_phase_v4a --common-changed
--phase1-changed`: PASS.

## How phase1.md was shortened and checked (workflow wf_9813e491-ee9)

- A writer shortened v4's phase1.md under fixed rules: only redundancy cut; nothing added or made more or less specific;
  steps, rubric questions, rule bullets and their order kept; the OUTPUT block byte-identical; the published rubric
  openings and every "If the first part holds" kept; and 14 phrases that v3/v4's results depend on kept word for word
  (C1n's OR-merge and instance clauses, C2's "do not name" sentences and its not-a-pacing-pulse list, step 3's compare
  kinds, the Hand-offs list, "Phase 2 sees only kept concepts ..."). Where a line was unchanged from v2, v2a's already
  checked shortening was reused.
- Meaning check: v4's phase1.md split into 103 clauses (`analysis/prompt_builds/v4_phase1_clauses.json`); two blind
  checkers judged every clause: 103/103 and 102/103 "same meaning"; the one "weaker" clause was revised and passed a
  re-check.
- Code check `analysis/prompt_builds/check_v4a_phrases.py` (self-test: all 14 phrases present in v4): all 14 present in
  v4a, "If the first part holds" 4 of 4, no "If so", OUTPUT block identical, rule heads in order: PASS.
- phase1.md shrank only 4% (v3 had already compressed it to pay for its additions); most of v4a's brevity is in common.md
  (17% fewer words), so most of a v4a-vs-v4 difference, if any, would come from common.md, which both phases read.

## How to read the run

- Falsified (brevity hurts) if v4a's precision, recall or found-in-all-runs count fall outside v4's run-to-run range
  (v4 r0-r2: precision 0.281-0.315, recall 0.817-0.835, correct finds 89-91, bus-record false positives 7-36), or if the
  merged bus-response concepts (pattern E1, CX5) come back in more than one run, as they did in v2a.
- Notebook: in cell 9 set `JOBS = [("two_phase_v4a", r) for r in (0, 1, 2)]` and `RUN_MANY = True`.
- Reminder: the ARROWS key line in all 43 diagram.txt files is looser than common.md 1(c) and 2.2. A fix is prepared
  for the next version (inputs v1k): `analysis/prompt_builds/DIAGRAM_KEY_FIX.md`.
