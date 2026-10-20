# two_phase_v3 — specific, non-conflicting Phase 1 at fixed length (2026-10-12, not run)

Base: `two_phase_v2`. **Only phase1.md changes** (common.md, phase2.md and both user templates are byte-identical to v2).
Goal: close the six scope gaps of `analysis/two_phase_v2__gpt-5.6-luna__high__r0-r2/V3_PHASE1_PROPOSAL.md` (section 4) with
specific language, using the user's techniques: testable criteria, explicit "If the first part holds" instead of "If so",
causal mechanisms, and compression to pay for the additions (phase1.md 1,433 -> 1,506 words, +5.1%).

System prompts (check_lab_prompt, clean): Phase 1 36,152 chars, sha12 `b513d32b7f64` (v2: 35,814, `df44fe84b87d`); Phase 2
unchanged `28a7f02c3a71`. `analysis/prompt_builds/build_check.py two_phase_v3 --phase1-changed`: PASS (OUTPUT block identical
to v2 apart from the "merged into Cn" placeholder; no JSON key missing).

## What changed (19 changes; full log with old/new text: `analysis/prompt_builds/v3_changelog.json`)

- Step 3: a compare whose result picks or triggers what happens next (stored state vs a request, a count vs a stored limit,
  a written value vs a fixed value) is its own piece, never merged into its inputs or the action it triggers (C5; gap 1).
- Rubric: each "If so" now reads "If the first part holds"; availability names the consequences inside the question
  (a port blocked, a required transfer lost, the IP or IC halted). The clock/reset sentence of line 16 now lives only in the
  Clocks and resets rule, which applies under every question.
- Step 5: Phase 2 sees only kept concepts and starts from their held lines (gap 5); step 6 compressed.
- Rules: Pacing pulses = C2 (+ "a start pulse decoded from a received command" is not a pacing pulse); Forwarded
  transactions = C1n (+ the word "bus" before "responses"); Working values = C2's synchronizer sentence; new Hand-offs rule
  (C6: a wait or fault flag, a write-enable flag or an access address that one instance hands on, on a non-record port, is
  its own piece); OUTPUT placeholder "merged into Cn, where Cn is a kept id" (C7). Bus handshake copies stays as in v2.
- Left as in v2 on purpose: step 2's lists, the published rubric openings, Build-time values (C22, the password under
  confidentiality, is the user's decision).
- Three skeptics found 28 problems (3 conflicts, 8 scope gaps, 6 vague terms, 4 implicit relations, 2 boundary losses,
  5 minor); the reviser fixed or rejected each with a reason (rejections listed in the change log).

## Decision-boundary check (user's technique 5), blind, on the stored v2 runs

Two judges per module read the final v3 text and decided, for each of the 307 v2 concepts, whether v3 would stop it and
which primaries would leave it; 8 modules with differences were adjudicated (workflows wf_fbb007f7-14b, wf_92765d1c-576,
wf_d423b81c-b70; `analysis/prompt_builds/v3_boundary.py`).

| run | extra concepts removed | matched concepts removed | FP elements removed | correct finds lost | correct finds moved to a new piece v3 asks for | precision estimate | recall |
|---|---|---|---|---|---|---|---|
| r0 | 3 | 0 | 123 | 0 | 4 (cpu alu_add, lsu_wait, lsu_err, pmp_fault) | 0.200 -> 0.281 | 0.780 |
| r1 | 0 | 0 | 23 | 0 | 5 (cpu lsu_wait, lsu_err, lsu_mar, pmp_fault; trng valid_o) | 0.244 -> 0.261 | 0.780 |
| r2 | 0 | 0 | 14 | 0 | 1 (cpu pmp_fault) | 0.246 -> 0.256 | 0.798 |

A filter on stored replies: it cannot show what v3 ADDS (the new pieces for computed decisions and hand-offs), which is
where its recall gains should come from.

## What it breaks / how to read it

- New Phase 1 hash; compare with v2 only (same model, effort, three runs). Removals and recoveries are in one version, so
  their effects cannot be told apart per change (the earlier v3a/v3b split was folded into one v3, as asked).
- Falsified if: a concept made of OR-merged bus responses appears again; a correct find drops below its v2 count (trng
  data_o 3/3, bus alu_res and keeper.err 3/3, cpu lsu_err and lsu_wait 2/3); or the targets of the new pieces (cache hit and
  watchdog timeout, now 0/3; bus a_req/b_req 2/3; cpu lsu_mar and alu_add 1/3; trng valid_o 1/3) are found in no more runs.
- Reminder: the ARROWS key line in all 43 diagram.txt files is looser than common.md 1(c) and 2.2; the Hand-offs and
  forwarded-transaction rules turn on "carries" versus "only decides".
- Notebook: set `VERSION = "two_phase_v3"`. Runs go to `runs/two_phase_v3__v1/<model>__<effort>/r<k>`.
