# two_phase_v2a — brevity test (2026-10-12, not run)

Base: `two_phase_v2`. **Only wording is shorter; the instructions are meant to be the same.** It answers one question:
does brevity alone change the model's output? Compare with v2 only (same model, effort, three runs).

| File | v2 words | v2a words | Change |
|---|---|---|---|
| common.md | 4,874 | 4,057 | 17% shorter |
| phase1.md | 1,433 | 1,288 | 10% shorter (the OUTPUT block is byte-identical) |
| phase2.md, phase1_user.md, phase2_user.md | | | byte-identical to v2 |

System prompts (check_lab_prompt, clean): Phase 1 31,209 chars, sha12 `690b07ad1c3f` (v2: 35,814, `df44fe84b87d`);
Phase 2 35,652 chars, sha12 `50e1406d640d` (v2: 39,552, `28a7f02c3a71`).

## How it was made (workflows wf_18c9ed67-578 and wf_d7237450-4b6)

1. Two writer agents shortened common.md and phase1.md under fixed rules: no instruction, example or criterion added;
   nothing more or less specific; ambiguities left alone; same section numbers, step numbers and rule bullet heads; every
   quoted literal, closed-set tag, JSON key, the OUTPUT block, "Return only the final JSON object" and the published
   rubric openings kept word for word. A second pass cut further under the same rules.
2. Meaning check, clause by clause: v2 was split into 371 numbered clauses (`analysis/prompt_builds/clauses.py`, self-test
   inside; 265 in common.md, 106 in phase1.md). Two blind checkers per part judged each clause of the new text: same
   meaning, weaker, stronger, changed or missing. First check: common.md 512 same / 15 weaker / 2 stronger / 1 missing;
   phase1.md 202 same / 9 weaker / 1 stronger (two checkers, so each clause is judged twice). A reviser fixed the flags;
   a re-check of every flagged clause left one "weaker" clause (common.md 63.2), which I restored by hand to the v2 words.
3. Code checks (`analysis/prompt_builds/build_check.py two_phase_v2a --common-changed --phase1-changed`): PASS.

## What it breaks / how to read it

- Both phases read common.md, so v2a shortens Phase 2's system prompt too. A difference from v2 is a brevity effect on
  the whole chain, not on Phase 1 alone.
- The cuts that are most likely to matter, if v2a differs from v2 (the writer's own list): statements that appeared twice
  now appear once (for example the index rule in 1(b) and 2.2, "a port map is drawn like an assignment", the [logic] block
  name note).
- Falsification: if v2a's Phase 1 concept counts per cluster, extra concepts, and structural precision and recall all
  stay within v2's run-to-run range (v2 r0-r2: precision 0.200-0.246, recall 0.780-0.798, extras 30/37/33), brevity alone
  does not matter here. If they move outside it, the change is a brevity effect (or a meaning slip the check missed;
  read the flagged clauses first).
- Notebook: set `VERSION = "two_phase_v2a"`. Runs go to `runs/two_phase_v2a__v1/<model>__<effort>/r<k>`.
