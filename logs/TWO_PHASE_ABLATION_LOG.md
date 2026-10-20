# Precision study with the two-phase prompt, 10 to 19 October 2026: ablation log, short form

The third prompt study of the LAsset replication (Algorithm 1 line 5, asset generation) on NEORV32. Objective:
precision with a recall guard, after study 1 (recall, `logs/RECALL_ABLATION_LOG.md`) had reached LAsset's recall by
listing three times as much, and study 2 had not closed the gap with a single call. The full record is
`experiments/03_two_phase_csa_pio/lab/EXPERIMENT_LOG.md` (EL: version table, standing rules, user decisions), `experiments/03_two_phase_csa_pio/lab/HANDOVER.md`
(HO: state at each hand-off), `experiments/03_two_phase_csa_pio/lab/analysis/v10_diagnosis/DECISION_LOG.md` (D1 to D107) and each version's
README under `experiments/03_two_phase_csa_pio/lab/prompts/`.

Every number below was re-derived on 2026-10-20 from the stored runs (`experiments/03_two_phase_csa_pio/lab/runs/two_phase_<v>__v1/`, local,
not published) by `experiments/03_two_phase_csa_pio/two_phase_ablation_log.ipynb`, with the lab's exact scorer (`compare_v8.score`,
self-test PASS). A figure marked (log) comes from the logs and was not re-derived: judge readings, blind-test
estimates, rule-firing counts and element lists read by the per-version scripts. Precision = correct / listed;
recall = correct / findable (reference entries whose name is in the module's closed set: 109 per run on the 15
tuning modules, 187 on the 26 held-out, 296 on all 41). Pooled = summed over the three runs. Three runs per version;
the run-to-run spread on the held-out set is about ten correct finds, so a smaller difference is inside noise.

## Prompt technique and structure

- **Technique.** Prompt chaining in the shape of IEEE P3164's method: two calls per module, gpt-5.6-luna at reasoning
  effort `high`, zero-shot (no worked examples), JSON replies. Phase 1 names the *conceptual* assets: each piece of
  information the unit holds or moves, judged by the four CSA questions (confidentiality, integrity, availability,
  undermined behaviour), with its objectives, the ports it enters and leaves through, and the RTL lines that hold it.
  Phase 2 takes Phase 1's list as written and, per concept, walks the block diagram as points of observation and
  influence, answers the four PIO questions at each block, names the closed-set elements that store, carry, produce or
  control the concept there, and labels each primary (the one element per place where the information is) or
  secondary (a path to it). Only primary rows are scored. From v5f the reply uses readable keys in the style of
  LAsset's result file, each key once, rows grouped under their concept.
- **System prompt = `common.md` + `phase<k>.md`.** `common.md` (shared by both phases): 1 WHAT YOU ARE GIVEN;
  2 DEFINITIONS 2.1 to 2.9 (objectives, information flow, the asset test, conceptual and structural asset, primary and
  secondary, points of observation and influence); 3 ASSUME THE SECURITY OBJECTIVES; 4 INDICATORS (SA-EDI types,
  SAIF's primary-asset examples, Nath & Tan patterns, high-risk structures). `phase1.md`: six steps (Interface, Inside,
  Merge and split, Rubric, Keep, Anchor), then the rule blocks, then OUTPUT. `phase2.md`: five steps (Walk, Questions,
  Structural assets, Primary with its bars and keep blocks, Secondary), then OUTPUT. Every Phase 1 rule has a Phase 2
  copy from v6 on. Sizes: v1 33,961 / 39,552 characters (1 named rule block), v7 58,561 / 68,286 (24), v9j 90,206 /
  98,361 (45), the working version 91,759 / 98,852 (46). Words `phase1.md` / `phase2.md` / `common.md`: v1 1,099 /
  2,079 / 4,874; working version 11,729 / 12,830 / 4,265. The sha12 of each system prompt is stored with every reply;
  the notebook recomposes all 38 run versions from their folders and every stored sha matches.
- **Inputs (the user message).** Three files per module, built by code from the RTL with no model
  (`src/pio_diagram/pio_inputs.py`, inputs v1, 2026-10-10): (1) the RTL with comments removed, blank lines left out and each
  line numbered as in the source; (2) the closed set as compact JSON: every port and signal of every entity, record
  fields by dotted name, occurrence lines, role tags (clock, reset, condition, selector, copied, operand, ...) and
  counterparts (gets value from, decided by, clocked by, ...); (3) a block diagram: labelled processes, generates,
  concurrent assignments and instances as blocks, arrows `==>` for a value and `-->` for a decision, each labelled with
  the elements it carries. Phase 2 adds Phase 1's "Conceptual Assets" list. Over the 41 modules: RTL 30.9%, closed set
  61.5%, diagram 7.5% of 1,851,463 characters; the watchdog's Phase 1 message is 22,203 characters. One input ablation
  only (v1k, the exact diagram key line); every other run used inputs v1.
- **Scoring and splits.** Exact: a listed name counts when it equals a reference name, each entry at most once, no
  credit between a record and its fields (study 1's strict scorer gave record-to-field credit). LAsset's split: 15
  tuning, 26 held-out. From 2026-10-14 the 12 held-out modules that caused v7's drop joined the tuning set
  (`tuning_v2`, 27 modules, 206 findable per run; `heldout_v2` the other 14, 90). Comparators on the same scorer:
  LAsset's RTL-only initial list 0.672 / 0.752 (precision / recall) on the tuning 15, 0.724 / 0.759 held-out, 0.704 /
  0.757 all 41; its spec+RTL list 0.730 / 0.917, 0.730 / 0.866, 0.730 / 0.885.

## Fixed before the study

- The closed set is built by code; the prompt names only its elements. `check_lab_prompt` rejects corpus identifiers,
  banned words and numeric emission hints, with a planted-error self-test, before any version runs.
- One folder per prompt version and per input version, never edited once it has runs; runs of two versions are never
  pooled in one metric; a version whose Phase 1 replies are copied from another (v5g, v6b, v6d, v6e) says so.
- Readings set before each run, in the version README or the run script's docstring, with the cut written down; three
  runs; verdicts on found-in-all-3, module-level sign tests and pooled counts, never on one run.
- Every rule needs a published basis (P3164, SA-EDI, SAIF, Nath & Tan, LAsset). Exception, logged each time as a user
  decision: bars that follow the reference's convention (the U rules 2026-10-12; D11 2026-10-16; the two convention
  bars of v9j, D86; the debug-registers bar, D95).
- Code is an instrument, not a filter: no post-filter between Phase 2 and the scorer (the P1-P4 code filters were held
  on 2026-10-14, "the task at hand is prompt debugging").
- Paid calls are sent by the user from the notebook; `chain.run_many` stores each reply with its prompt sha as it
  arrives and never asks a stored reply again.

## Results

Pooled precision / recall (runs: correct/listed per run). USD = the version's stored luna usage at list prices, both
phases, all runs (a Phase 2-only version repeats its source's Phase 1 spend).

| version (arm) | change | tuning 15 | held-out 26 | USD | decision |
|---|---|---|---|---|---|
| v1 (A-01) | the user's definitions, P3164 rubric and PIO questions | 0.179 / 0.804 (88/480, 87/481, 88/510) | 0.239 / 0.822 | 5.89 | base |
| v2 (A-02) | Phase 1 rules A1-A6 | 0.228 / 0.786 (85/425, 85/349, 87/354) | 0.244 / 0.779 | 5.53 | pass, promoted |
| v2a (A-03) | v2 in shorter wording | 0.210 / 0.798 (85/382, 87/425, 89/434) | | 2.09 | null (brevity is not a lever) |
| v3 (A-04) | specific Phase 1 at fixed length | 0.235 / 0.841 (92/393, 94/371, 89/405) | | 2.16 | pass, promoted |
| v4 (A-05) | 2.6: bus record ports never primary | 0.295 / 0.826 (90/286, 91/313, 89/317) | | 2.22 | pass, promoted |
| v4a (A-06) | v4's content in v2a's wording | 0.300 / 0.832 (94/320, 84/295, 94/293) | 0.275 / 0.788 | 5.88 | rule fired by r1; promoted (user) |
| v4a on v1k (I-1) | exact diagram key line (inputs only) | 0.311 / 0.807 (88/280, 90/289, 86/280) | | | fail; key kept out |
| v5 (A-07) | rules A, B, U1-U12 + 13 conflict fixes | 0.383 / 0.792 (91/246, 81/216, 87/214) | 0.318 / 0.740 | 5.70 | precision pass, recall fails; promoted |
| v5f (A-08) | reply format only | 0.416 / 0.827 (6 runs: 91/206, 85/214, 92/220, 94/188, 91/244, 88/228) | | 4.46 | pass, promoted |
| v5g (A-09) | Phase 2 consistency fix | 0.430 / 0.813 (82/172, 89/222, 95/224) | | 2.23 | null; base of v6 |
| v6 (A-10) | 24 paired rules | 0.620 / 0.780 (86/143, 83/134, 86/134) | 0.426 / 0.652 | 5.61 | pass, promoted |
| v6a, v6b, v6c, v6abc (B-1 to B-4) | condensed by part | 0.604 / 0.722; 0.607 / 0.771; 0.579 / 0.752; 0.625 / 0.722 (6) | | 2.07; 2.10; 2.15; 4.20 | v6b held, the others fired; none adopted |
| v6d (B-5) | v6abc + one unit restored | 0.617 / 0.774 (86/143, 84/131, 83/136) | | 2.08 | pass; final condensed prompt (user) |
| v6e (B-6) | v6 + part of v6b | 0.604 / 0.774 (87/147, 84/135, 82/137) | | 2.14 | precision fired narrowly; not adopted |
| v7 (A-11) | exceptions inside each rule's main sentence | 0.614 / 0.817 (92/146, 89/158, 86/131) | 0.375 / 0.697 | 5.82 | pass; final prompt (user, 10-13) |
| v8 (A-12) | seven rules from v7's failures | 0.664 / 0.841 (92/133, 95/143, 88/138) | 0.400 / 0.688 | 5.76 | tuning readings held; held-out recall down |
| v9 (A-13) | Forwarded transactions narrowed | 0.660 / 0.850 (96/152, 89/134, 93/135) | 0.401 / 0.713 | 5.86 | pass (R7 falsified); working version 10-14 |
| v10 (A-14) | 17 rules rewritten as blocks | 0.647 / 0.826 (90/146, 90/136, 90/135) | 0.403 / 0.679 | 5.84 | fail (V1, V3); v9 stays |
| v11, v11h, v12 (A-15 to A-17) | merged rule fixes, one run each | 0.676 / 0.844; 0.688 / 0.807; 0.611 / 0.807 | 0.454 / 0.652; 0.403 / 0.674; 0.420 / 0.706 | 2.27; 2.04; 2.00 | r0 gates: fail, fail, pass inside noise; v9 stays |
| v9f (A-18) | five Phase 1 rule fixes on v9 | 0.667 / 0.862 (r0 only) | 0.416 / 0.706 (138/357, 130/291, 128/304) | 4.59 | fail; v9 stays |
| v9g (A-19) | + five keep rules N21-N25 | 0.687 / 0.844 (r0) | 0.509 / 0.824 (153/293, 153/288, 156/326) | 4.41 | pass; candidate |
| v9h (A-20) | + keep blocks K11-K14 | 0.617 / 0.872 (r0, r1) | 0.506 / 0.848 (r0, r1) | 4.31 | null; recall up, precision down |
| v9i (A-21) | - K14, + five bars | 0.660 / 0.872 (r0) | 0.602 / 0.818 (r0) | 2.65 | precision up, recall cost; not as is |
| v9j (A-22) | control-unit bar spares ports; keep blocks last | 0.697 / 0.865 (93/130, 94/145, 96/131) | 0.569 / 0.848 (162/296, 159/273, 155/268) | 5.91 | pass; working version 10-18 (D86) |
| v9k, v9l, v9m (A-23 to A-25) | the walk precedence, three placements | 0.692 / 0.899; 0.694 / 0.865; 0.682 / 0.832 | 0.570 / 0.850; 0.569 / 0.827; 0.540 / 0.831 | 6.00; 6.00; 5.93 | gate fail x3; track closed (D91) |
| v9n screens A, A2, B, C, E (S-1) | six overnight candidates | | 0.662 / 0.843; 0.661 / 0.816; 0.549 / 0.861 (1); 0.554 / 0.845 (1); 0.581 / 0.877 (2) | 13.65 (log) | only A moves precision; A = working version (D94) |
| v9n_place_dbg (A-26) | A + paired debug bar, after the control-unit bar | | 0.670 / 0.802 (155/229, 148/232, 147/211) | 3.68 | fail (recall); not adopted |
| p1o_first (A-27) | A + the debug bar FIRST in Phase 1 | 0.741 / 0.856 (95/125, 90/115, 95/138) | 0.689 / 0.838 (159/226, 162/228, 149/228) | 5.73 | pass; WORKING VERSION (D103, D107) |
| LAsset RTL-only list (published) | | 0.672 / 0.752 (82/122) | 0.724 / 0.759 (142/196) | | |

All 41, pooled over three runs: p1o_first 0.708 / 0.845 (750 of 1,060 listed, of 888); v9j 0.611 / 0.855; LAsset
RTL-only 0.704 / 0.757. Found-in-all-3 on the exact scorer, tuning 15: v1 75, v2 64, v2a 70, v3 77, v4 77, v4a 79,
v4a-v1k 68, v5 67, v5f 79 (the logs' pack-based counts run 2 higher, same differences).

## Arms

### A-01, v1: the method as written
No cut registered; the README lists what to read (P and R of the primary rows, Phase 1 kept vs not kept, Phase 2 points
per concept). A pilot and one full run on gpt-5.4 first (USD 27.35, P 0.189 R 0.766 of 111, log); luna from here on.
Got: four of five listed elements are not in the reference; 280 of 526 distinct false positives recur in all three
runs (log): whole transaction records, port fields, siblings of listed settings. Next: A-02.

### A-02, v2: Phase 1 rules A1-A6 (clocks and resets, build-time values, pacing pulses, forwarded transactions, bus handshake copies, working values)
Before the run: falsified if the targeted concept clusters keep more than half of their v1 concepts, or if recall falls
below 0.780 (the lowest filtered estimate on v1's stored replies) in two of three runs. A1 has no published basis
(user decision 2026-10-12). Got: targeted clusters kept 21 of 120 concepts (log); recall 85 / 85 / 87 of 109, no run
below the cut, "at the boundary"; precision 0.179 to 0.228; module sign test 4 up, 7 down, p 0.55. Whole bus records
gone, bus port fields in their place (163 of 200 new false positives, log). Pass; promoted. Next: A-03 and A-04, both
against v2.

### A-03, v2a: same meaning, fewer words (common.md 4,874 to 4,057 words)
Before the run: brevity alone does not matter if precision, recall and extra concepts stay inside v2's run-to-run range
(precision 0.200 to 0.246, recall 0.780 to 0.798). Got: precision 0.223 / 0.205 / 0.205, all three inside; recall r2
0.817 above; extra concepts 41 / 37 / 40 against 30 / 37 / 33 (log); element sign test p 0.53 (log). Null on
structure; not a lever; its short common.md reused in v4a. Next: A-04.

### A-04, v3: specific Phase 1 at fixed length (C1n, C2, C5, C6 hand-offs, C7, "If the first part holds")
Before the run: falsified if OR-merged bus responses reappear as a concept, a correct find drops below its v2 count,
or the targets of the new pieces are found in no more runs. Got: correct 92 / 94 / 89 against v2's 85 / 85 / 87;
recall 0.841 against 0.786, precision 0.235 against 0.228; modules 10 up, 2 down, p 0.04; found-in-all-3 64 to 77.
Two falsifier items tripped (trng data_o 3 to 2 runs; the merged concept back in r2) and the report did not call the
version falsified. Pass; promoted. Next: A-05.

### A-05, v4: one line in 2.6, bus request and response record ports and their fields are never primary
Before the run: falsified if bus record ports or fields are still primary, or a plain port behind a bus port drops below
its v3 count. Basis measured on v2's stored runs: record ports and fields were 176 / 71 / 101 of the false positives
and 0 of the correct finds (log). Got: precision 0.295 (every run above v2's highest); recall 0.826 against 0.841,
modules 4 up, 6 down, p 0.75; record false positives 7 / 19 / 36 per run, not zero (log); csr_wdata_i 3 to 2 runs.
Partly tripped, not called falsified. Pass; promoted. Next: A-06.

### A-06, v4a: v4's content in v2a's wording (common.md 4,926 to 4,109 words)
Before the run: brevity hurts if precision, recall or found-in-all-3 fall outside v4's range (precision 0.281 to 0.315,
recall 0.817 to 0.835), or merged bus-response concepts return in more than one run. Got: recall 0.862 / 0.771 /
0.862, r1 below the range (84 correct); precision 0.294 / 0.285 / 0.321; found-in-all-3 77 to 79. The dip is r1
being the worst run in 8 of 9 modules at once (permutation p 0.022, log), not within-module noise; it did not recur on
v1k. Rule fired by one run; averages equal; promoted as the base of v5 (user, 2026-10-12). Next: I-1 and A-07.

### I-1, v4a on inputs v1k: the exact diagram key line
Before the run: the exact key hurts if found-in-all-3 drops. Got: precision 0.311 against 0.300; recall 0.807 against
0.832; found-in-all-3 79 to 68 on the exact scorer (log: 81 to 70, 18 lost, 7 gained, p 0.043); misses labelled only
secondary 26 to 37, with "decides" reasons 14 to 24 (log). The targeted error (a prescaler said to carry a value) never
occurred, even on v1. Fail; user decision 2026-10-12: keep the key out, build v5 on inputs v1.

### A-07, v5: rules A (R1 R3 R4 R5 K1 K2), B (R2b R7b), U1-U12 and 13 conflict fixes (phase1.md 1,448 to 2,790 words)
Before the run: precision falsified if not above v4a's range (0.285 to 0.321) in two of three runs; recall falsified
if any element found in all three v4a runs is found in fewer than two v5 runs, or recall falls below v4a's range
(0.771 to 0.862); overfitting read on the held-out 26 against v4a. The U rules are reference-convention restrictions,
logged as a user decision ("if reference doesn't list them, and they don't ... contribute to any TP, then remove
them"). Blind estimate on v4a's stored replies: precision 0.519 / 0.503 / 0.540, 0 correct lost (log). Got: precision
0.370 / 0.375 / 0.407, pass; recall 0.835 / 0.743 / 0.798, r1 below the range (a bus reply put the element in the
wrong key; repaired r1 0.798, log); element test fails (6 strictly, 3 with the repair). Held-out: recall 0.788 to
0.740, the overfitting falsifier fired. 14 of the 20 rules failed their own test; Phase 1-only rules leak through
Phase 2 (log). Promoted with the rules unchanged. Next: A-08 (stop the slip), then A-09.

### A-08, v5f: the reply format only (readable keys, each key once, rows under their concept, primary or secondary as a label)
Before the run: falsified if replies with nameless asset rows are not fewer than v5's 3 to 5 of 45, or if precision or
recall falls below v5's lowest run in two or more runs, or three or more elements found in all v5 runs are found in at
most one v5f run. Got: slip 4 of 45 to 0 of 45 (log); precision 0.442 / 0.397 / 0.418, above v5 in every run; recall
0.835 / 0.780 / 0.844, equal, up, up; found-in-all-3 67 to 79; element rule fired on four elements (bus stb, the
multiplier's two start flags, imem rdata), diagnosed as chance or unclear (log). Pass; promoted. Next: A-09.

### A-09, v5g: Phase 1 / Phase 2 consistency fix in phase2.md only (2,278 to 4,606 words)
Before the run: against the control v5f r3-r5 on the same Phase 1 replies: precision up in two of three pairs, recall
not down in two of three, no reference element lost. The copy script was not applied, so all nine were full runs and
the comparison became v5g against v5f's six-run range (log). Got: precision up in 2 of 3 pairs, recall not down in 1 of
3; pooled 0.430 / 0.813 against 0.416 / 0.827; every v5g run inside v5f's range. r0's bus reply nested the asset rows
inside the points (repaired r0 recall 0.835, log). Null; lesson: a bar that exists only in Phase 2 is ignored once Phase
1 has built the concept. Base of v6 by user decision. Next: A-10.

### A-10, v6: 24 paired Phase 1 / Phase 2 rules from v5g's failures (phase1.md 2,849 to 6,200 words, phase2.md 4,606 to 7,863)
Before the run: precision above 0.500 in two of three runs; two or more runs below 0.780 (v5f's lowest) falsifies "the
rules do not cost recall"; an element found in five of v5f's six runs and two of v5g's but at most one v6 run is a loss
to trace. Blind boundary test: 0 correct lost, 21 gained, 246 false positives removed, an upper bound (log). Got:
precision 0.601 / 0.619 / 0.642, three of three; recall 0.789 / 0.761 / 0.789, one run below; pooled 0.620 / 0.780
against v5g's 0.430 / 0.813. Ten elements lost, most to rules applied beyond their trailing exception lists (log).
Held-out, run later: 0.426 / 0.652. Pass; promoted. Next: B-1 to B-6 (brevity, user request) and A-11.

### B-1 to B-6, v6a, v6b, v6c, v6abc, v6d, v6e: condensing v6 by part (about 5% shorter per file)
Before the runs: for each, two or more runs below 0.761 (v6's lowest recall) or below 0.601 (v6's lowest precision)
falsifies; element losses traced to a condensed sentence and its v6 wording restored. v6b, v6d and v6e are Phase 2-only
runs on copied Phase 1 replies. Got (pooled against v6's 0.620 / 0.780, 255 correct of 327): v6a (phase1.md) 0.604 /
0.722, recall fired; v6b (phase2.md) 0.607 / 0.771, held; v6c (shared sentences) 0.579 / 0.752, both fired; v6abc (all
three) 0.625 / 0.722, recall fired. Phase 2 drawn twice on the same concepts moves a run by 0 to 5 correct finds
(v6abc r3-r5, the spread test), the noise bar from here on. v6d (v6abc with one traced unit restored) 0.617 / 0.774,
253 correct: level with v6, module sign test p 1.00; v6e 0.604 / 0.774, precision fired by 0.009 and 0.002. "Condensing
Phase 1 costs recall" was withdrawn: losses cluster by reply, and module-level tests give p 0.09 or more for every
condensed version. User decision 2026-10-13: v6d is the final condensed prompt. Next: A-11 on v6d.

### A-11, v7: five narrowings, each rule's exception inside its main sentence (CX2.U3b, CX4.TF1, CX1-ACF, P11.5, LS1)
Before the run: at least 5 of the 10 elements v6 lost found in two or more runs supports the narrowing; two or more runs
below 0.761 falsifies, two or more above 0.789 supports a gain; two or more runs below 0.601 falsifies. Got: recall
0.844 / 0.817 / 0.789, two runs above 0.789; precision 0.630 / 0.563 / 0.656, one run below 0.601; 6 of 10 lost
elements back in two or more runs, 19 of 30 element-runs against 4 of 30 (log); pooled 0.614 / 0.817 against v6's
0.620 / 0.780, run-level p 0.15 (log). Not recovered: the bus's two request lines, imem addr, sys enable_i. All
readings held; pass. User decision 2026-10-13: v7 is the final prompt. Held-out, run the next day: 0.375 / 0.697
against v6's 0.426 / 0.652. Next: A-12 from v7's failure analysis.

### A-12, v8: seven rules from v7's failure analysis (B1, R1-R6; phase1.md 5,963 to 6,979 words)
Before the run: at least 5 of 10 target elements found in two or more runs; recall below 0.789 in two or more runs
falsifies, above 0.844 supports; precision below 0.563 in two or more runs falsifies; B1's own falsifier; element
losses; held-out recall or precision below v7's shows the rules fit the tuning modules only. Blind test on v7's stored
replies: recall 0.817 to 0.914, 0 lost, an upper bound (log). The four code filters P1-P4 were held (user: "the task
at hand is prompt debugging"). Got: recall 0.844 / 0.872 / 0.807, none below 0.789, one above 0.844; precision 0.692 /
0.664 / 0.638, none below 0.563; pooled 0.664 / 0.841 against 0.614 / 0.817. Held-out 0.400 / 0.688 against v7's
0.375 / 0.697: recall down, the last reading fired. Base of v9. Next: the held-out diagnosis, the tuning_v2 split, A-13.

### Held-out diagnosis and the tuning_v2 split (diagnostics, 2026-10-14)
Held-out recall by version: v1 0.822, v2 0.779, v4a 0.788, v5 0.740, v6 0.652, v7 0.697, v8 0.688 (tuning 0.780 to
0.841). The drop comes at v4a to v5 and v5 to v6; the lost finds trace to Phase 1 rules applied beyond their text
(Access command fields, Forwarded transactions, Port buffers, Sequencing state, Buffer and engine status bits); the
false positives v7 and v8 keep come from 2.6 and field-level naming (log). The v1 to v2 held-out loss is one module,
xbus (27 to 9 correct, log), which gave A-13. Twelve held-out modules carry the degradation (nine CPU sub-units,
debug_dm, pwm, xbus); they joined the tuning set as `tuning_v2` (v7 there 0.401 / 0.712; `heldout_v2` 0.574 / 0.807,
chosen by v7's result, so it overstates generalisation).

### A-13, v9: the Forwarded transactions rule narrowed (a bus whose address and acknowledge sit on the unit's own non-record ports; by port name only xbus)
Before the run, on seven modules: R1 the three xbus data and strobe ports found in two or more runs (v8 0 of 3 each)
supports, none falsifies; R2 the address and write-enable ports stay; R3, R4, R6 no loss on the bus, cache, CPU and
CSR modules; R7 debug_dtm correct not down (13) and false positives not up (20). Got, seven modules: xbus correct 12 to
18, false positives 19 to 17; R1 supports (two ports in two runs, one in one); R7 falsified (debug_dtm false positives
20 to 28, no reply invokes the clause, likely spread) (log). All 41: tuning 0.660 / 0.850 against v8's 0.664 / 0.841;
held-out 0.401 / 0.713 against 0.400 / 0.688. Pass except R7; the working version from 2026-10-14. Rule consistency
on v9: bar violations explain 0.41 of tuning false-positive runs but 0.11 of held-out ones; 17 of 56 inconsistent cases
are a rule over-applied, 8 a rule ignored (log). Next: the rule-isolation diagnostics, then A-14.

### Rule-isolation diagnostics (not arms, 2026-10-14 to 10-16)
Each rule run alone on each module, Phase 1 and Phase 2 wording, twice with identical input (stored replies: v9 4,836;
v10r 2,702; v10f 656; v10f2 328; v10f3 164; v10f4 and the six unseen modules 1,376; v10fo 656; costs USD 28.78, 17.63,
7.45, 4.06, 2.26, 6.57, 4.17, log). Found: 134 real ambiguities, 9 rules unclear, two bars clear alone but ignored in
the full prompt (log). Cause of over-application: resemblance plus the model not checking its own facts (69 of 90
classified cases, log); writing the facts first fixed Sequencing state and Port options but doubled the replies;
without the facts format (v10fo) the gain was too close to call (0.152 against a cut of 0.131 +- 0.030, log), so the
facts format stayed out (G3). The merged reading procedure passed on Claude (E3: 0.117 to 0.031, bar 0.157, log); the
status-bits fix showed no harm and no confirmed benefit (E1). Over-tuning: the held-out minus tuning gap went from
+0.06 / +0.02 at v1 to -0.26 / -0.14 at v9 (precision / recall, log); on six modules no fix was made from,
disagreement fell 42% (log). Every one of the 41 modules has now supplied fix cases.

### A-14, v10: the 17 unclear rules rewritten as blocks (Scope, Criteria, Exceptions, Outcome, Evidence) plus one shared reading procedure
Before the run: V1 on tuning_v2, pooled precision and recall each not below v9's by more than 0.02; V3 on heldout_v2 by
0.03; V4 the 17 Sequencing-state reference signals, a drop of more than 2 is a fail; V5, V6 watched. Got: tuning_v2
0.451 / 0.709 against v9's 0.440 / 0.739, V1 fails on recall (-0.030); heldout_v2 0.545 / 0.789 against 0.583 /
0.819, V3 fails (-0.038); V4 37 to 29, a drop of 8 (log). Fail; v9 stays. Diagnosis: the rules v10 breaks are
followed alone; breaks occur only where Phase 1 had already named the barred signal (a core / Phase 1 hand-off clash,
not rule against rule); in Phase 1, other rules' text undoes a rule, not length (D39); Operation selectors fixed alone
by moving it last with a precedence sentence (0.761 to 0.978, log), the bus record-port bar by moving it last (0.826
to 0.935, log); 366 of 711 false-positive pairs and 60 of 237 misses had no rule, and nine new rules passed alone under
D11 (reference-convention bars allowed, logged). Next: A-15.

### A-15 to A-17, v11, v11h, v12: the fixes that passed alone, merged (one run each, stop gates)
Before each run: stop after r0 if tuning_v2 correct is below 144 of 206 (v9's and v10's per-run spread) or precision
below 0.404, or heldout_v2 below 69 of 90 or precision below 0.530; v11 then M1 / M2 as v10's V1 / V3; v12 also its
targets (carry-over shown at 7 or more of 12) and N12's four false positives. Got: v11 (v10 + four carried fixes) r0
142 of 206, stop; v11h (v11's Phase 1 with v10's Phase 2, to separate the Phase 1 fixes from the Phase 2 moves) 142,
fail by two, the two Phase 2 moves dropped; v12 (v11h + the Phase 1 fixes that passed alone + N12) 146, gate pass
inside noise, targets 1 of 12, N12's targets 3 of 4 still listed (log). v10's own r0 (141) fails the same gate. Fail;
v9 stays. Lesson D71: "not barred" alone does not make a target primary; a keep-type fix has to say where the target
is held and label it. Next: A-18, the same rule texts written into v9 instead of v11h.

### A-18, v9f: five Phase 1 rule fixes on v9 (held-out 26, three runs)
Before the run: a rise is shown when every run is above v9's best (136 of 187), a drop when every run is below its
worst (130); at least 9 of 21 targets in every run. Got: 138 / 130 / 128, pooled 396 against v9's 400 of 561 (0.706
against 0.713), precision 0.416 against 0.401; targets 14 / 6 / 6 (log); r0 was a lucky draw. Fail; v9 stays. The
misses (165 entry-runs of 561): labelled secondary 73, never named in Phase 1 43, Not Kept 23, a field listed instead
of the record 16; every whole control-record port missed in every run while 101 of its fields were listed, all false
(log). Next: A-19, keep rules for those groups.

### A-19, v9g: five keep rules N21-N25 (control record ports, access command ports, entry selects and register addresses, boundary outputs, coprocessor progress state) and the Port buffers revision
Before the run: every run above both baselines' best (138) shows a rise; then a does-not-hurt check on the tuning
groups by v10's V1 cut. The rules passed alone on Claude Sonnet agents first (no OpenAI budget that day); N21, N23 and
N24 rest partly on the reference's convention (log). Got: 153 / 153 / 156, pooled 0.509 / 0.824 against v9f's
0.416 / 0.706; modules 15 up, 6 down (sign test p 0.08 here; the plan's own test gave p 0.002, log); tuning r0
0.687 / 0.844, tuning_v2 0.545 / 0.830, heldout_v2 0.655 / 0.822: does-not-hurt pass. Pass; candidate. The held-out set
is no longer independent from here: rules were written from its misses. Next: A-20.

### A-20, v9h: keep blocks K11 Done and wait inputs, K12 Link handshake ports, K13 Busy locks, K14 Count increment inputs, each right after the bar it overrides
Before the run, on a seven-module cell: a block is followed when every target is found in two of three runs; a change
counts when it holds in every run and moves at least 3 pooled correct finds. Got: K11-K13 followed 27 of 27 target-runs
(v9g 12 of 27), K14 0 of 3; pooled 127 against 123, no change shown (log); K12's exception sent the external bus data
lines to the Forwarded transactions bar. All 41, r0-r1: all-41 recall 0.856 against v9g r0's 0.828, precision 0.542
against 0.574 (r0 paired: 253 against 245 correct); tuning 0.617 / 0.872. Null; recall up on every group, tuning
precision down. 153 consistent false positives analysed in nine groups. Next: A-21.

### A-21, v9i: K14 dropped, K12's exception reworded, five bars added (Stored-word arrays, Processor control-unit state, Forwarded-access stages, Transfer records, Response merges)
Before the run (r0 only): precision above both v9h runs on tuning_v2 and the held-out 26, with recall not below the
lower v9h run by more than 0.02 on either. Got: held-out 0.602 / 0.818 against v9h's 0.506 / 0.848, tuning_v2 0.597 /
0.820; precision up on every group, held-out recall -0.03: not shown. 54 of the 153 consistent false positives gone;
16 reference entries lost, in the control-unit bar's neighbourhood (its output record and three inputs) and the
external bus's strobes (log). Two of the five bars rest on the reference's convention (D86). Next: the order cell
(keep blocks last: pooled 132 against 122 on the seven modules, no difference shown, log) and A-22.

### A-22, v9j: the control-unit bar spares the unit's ports and output record; every keep block last in its step (order B)
Before the run: on tuning_v2, recall and precision each not below v9g's by more than 0.02; "better than v9h" when
pooled precision is above v9h's on every group with recall not below by more than 0.02. Got: tuning 0.697 / 0.865;
held-out 0.569 / 0.848 (v9h r0-r1 0.506 / 0.848; v9g 0.509 / 0.824); tuning_v2 0.593 / 0.853; heldout_v2 0.654 /
0.859 against v9h's 0.671 (the one group short, by 0.017); all 41 0.611 / 0.855. Does-not-hurt pass. User decision
D86: v9j the working version; the two convention bars logged. False positives on v9j (484 over three runs): 78% extra
elements under right concepts in Phase 2, 22% extra configuration concepts; Phase 1 precision work closed; walk-found
internals 50 correct against 160 false (log). Next: A-23.

### A-23 to A-25, v9k, v9l, v9m: the walk-found-internals precedence, three placements
Before each run: tuning_v2 pooled precision at least v9j's +0.05 with recall at least v9j's -0.02; the rule simulated as
a post-filter gives tuning_v2 0.593 to 0.698 (log). Got: v9k (the bar last in step 4) 0.593 / 0.871 against v9j's
0.593 / 0.853, precision unchanged, the core sentence wins over a bar after it; v9l (the precedence in the core
sentence) 0.587 / 0.845, followed (walk-found false internals 88 against 156, log) but the false positives moved to the
held lines; v9m (v9l + a code-built LOCATED list as Phase 2 input) 0.563 / 0.814, followed exactly but the list became
a menu (45 new false positives from inside it) and the keep blocks lost (14 reference entries). Three gate fails. User
decision D91: track closed, no code post-filter; v9j stays. Next: S-1.

### S-1, overnight screens on the held-out 26 (v9n_place A, v9n_place2 A2, v9n_conf B, v9n_cfg C, v9n_menu D, v9n_dbg E)
Before the runs: screen against v9j r0 (recall at least 0.82, precision at least 0.58), confirm with r1 and r2, final
cut pooled recall at least v9j's 0.848 with precision above 0.569; budget floor USD 4. Got: A (one primary per place
where the information is, in step 4's core sentence) 0.662 / 0.843 over three runs, 473 against v9j's 476 correct,
precision +0.093; A2 0.661 / 0.816; B (a confidence key) 0.549 / 0.861, one run, no signal; C (a Phase 1 settings
bar) 0.554 / 0.845, one run; D (the LOCATED list as a bound) one run on 25 modules, a runaway reply, not scored here; E
(the debug bar alone, last) 0.581 / 0.877, two runs, a favourable first draw and the bar did not fire. Only A moves
precision; it misses the recall cut by three finds, inside noise. User decision D94: A is the working version, v9j the
fallback. Next: A-26.

### A-26, v9n_place_dbg: A + the paired Debug module registers bar (Phase 1 after the control-unit bar, Phase 2 last)
Before the run: precision above A's with recall not below A's by more than 0.02; the debug module's listed count per
run and whether the bar is cited. The bar follows the reference's convention (user decision D95). Got: 0.670 / 0.802
against A's 0.662 / 0.843; modules 5 up, 16 down, p 0.03. The bar fired (debug module 41 false fewer over three runs,
reference kept 5 / 6 / 5 of 6, log) but 24 correct finds were lost elsewhere, spread over many modules, with the
external bus ports among them. Fail; not adopted; the debug cut stays a logged idea. Next: T-1, the position question
(user: does the new rule's position hinder the other Phase 1 rules?).

### T-1 to T-3, the position of one Phase 1 block (Phase 1-only runs, read by located share)
Located share = reference entries that Phase 1 locates (a port under Enters or Leaves Through, or an element assigned at
a held line) over findable; an upper bound on recall except for names Phase 2 finds on the walk; about USD 0.53 per
held-out run against 1.26 for both phases. Tier 1, before the runs: a position is acceptable when its pooled share is
within 0.01 of A's and the bar fires in the debug module in at least two runs; the three positions within 0.01 of each
other would falsify "position matters". Got (three runs each, 561 entries): A 0.836; the bar FIRST 0.825, 14 entries
located in more runs and 20 in fewer, sign test p 0.49, fires 3 of 3; after the control-unit bar 0.807, p 0.035; LAST
0.811, p 0.011, fires 1 of 3; a same-length sham at the second position 0.834, p 1.0. Position matters: first holds A's
share within noise (by the sign test; the 0.01 wording is missed by 0.001), the two later positions cost 0.025 to
0.029, the sham costs nothing, so the loss is the bar's content at that place. Tier 3, before the run: Phase 2 on the
first-position records, recall not below A's by more than 0.02 and precision not below A's. Got: p1o_first held-out
0.689 / 0.838 against A's 0.662 / 0.843 (470 against 473 correct), modules 8 up, 9 down, p 1.0; debug module false 2
against 51 (log). Pass. User decision D103 (2026-10-19 17:05): p1o_first the working version, A the fallback. Known:
the debug module's reset-request output is never found; the bar sits in Phase 1 only (its Phase 2 file is A's,
byte-identical). Tier 2, the order of all 46 blocks, five orders plus a wording fix, one Phase 1 run each: fix 0.824,
bars first 0.850, keeps first 0.813, hard-to-easy 0.840, easy-to-hard 0.856, rules after OUTPUT 0.861 against 0.824,
none significant; the two best over three runs 0.829 (p 0.85) and 0.832 (p 0.72) against 0.825, with larger candidate
pools (349 and 371 names against 336). Gate (share at least the working version's with volume not above) fails; Tier
2 closed; nothing adopted.

### A-27, p1o_first on the tuning 15 and all 41 (D107, 2026-10-19 evening)
Before the run: the held-out gain transfers if tuning pooled precision is above v9j's 0.697 with recall not below v9j's
lowest tuning run (0.853); it does not if precision is below v9j's lowest run (0.648); between is noise. Got: 95/125,
90/115, 95/138, pooled 0.741 / 0.856 (v9j 0.697 / 0.865); all 41 pooled 0.708 / 0.845 (v9j 0.611 / 0.855; LAsset's
RTL-only list 0.704 / 0.757); 90 calls, no failures, USD 2.11 (the version's stored total 5.73). Transfers. No
reference entry found in two or more v9j tuning runs is lost; 19 false names appear in all three tuning runs (log).
End of the study.

## Where the study stopped

- Working version: `two_phase_p1o_first`, all 41 pooled precision 0.708 / recall 0.845, against LAsset's RTL-only
  initial list at 0.704 / 0.757 on the same scorer and modules, and the study's v1 at 0.213 / 0.815. Fallbacks:
  v9n_place (held-out 0.662 / 0.843), then v9j (0.569 / 0.848).
- Held-out figures from v9g on are selection results, not out-of-sample: the keep rules were written from the held-out
  misses, and every version from v9f on was chosen on that split. The tuning 15 runs of the working version were made
  after the choice. No labelled NEORV32 module exists outside the 41.
- Three bars rest on the reference's convention, not a published basis (Stored-word arrays, Processor control-unit
  state, Debug module registers), each logged as a user decision; a change in the reference voids them.
- Registered and not run: the debug bar as the second Phase 1 block (about USD 0.5); the facts-first step for
  Sequencing state alone (the G3 fallback); the E1-style fixes for four other rules.
- Spend on the two-phase runs listed above, from stored usage: USD 144.35 (Phase 1 copies counted once); the
  rule-isolation runs about USD 71 more (log); the gpt-5.4 v1 run 27.35 (log).

## Corrections kept in the log

- "Condensing Phase 1 costs recall" (B-1, B-4): withdrawn; losses cluster by reply, module-level tests p 0.09 or more.
- v6d's recovery over v6abc (+9 / +8 / +4) is Phase 2 spread plus one broken uart reply, not the restored unit.
- v2's recall cut "0.780" was 85 of 109 rounded; read as "fewer than 85 correct finds".
- v4a's r1 dip was first called run-to-run variance; measured, it is one run worst in 8 of 9 modules at once.
- v5f "four times more Phase 1 merges": counted the same way, merges are equal in v5 and v5f.
- v5g's planned Phase 2-only design was not applied (full runs); read against v5f's six-run range instead.
- v9's per-port counter compared a bare name with module:name strings and read 0 everywhere until a per-element
  self-test was added.
- The precedence of Phase 2 bars over 2.6 was proposed as a fix on 2026-10-14 and was already in phase2.md:34.
- v10's "prompt length loads Phase 1" (D39): two control cells had been sent without the rule by a code bug; rule-like
  text, not length, is the cause.
- v9f r0 "robust targets, held-out recall rose" (D73): withdrawn over three runs (D74).
- The order-B builder placed keep blocks only approximately last (D85); v9i_orderB and v9j are measured as built.
- D103's "paired bar with its Phase 2 copy" describes v9n_place_dbg; the working version carries the bar in Phase 1
  only, and the wording fix was run once, Phase 1 only (D107).
- Blind boundary tests overstate: v6 predicted precision 0.70 to 0.77 and 0 lost, the run gave 0.60 to 0.64 and 10
  lost; v5g predicted 0.50 to 0.55, the run gave 0.43.

## Re-derived against logged

Every per-run correct and listed count, pooled precision and recall, the tuning_v2 and heldout_v2 figures and the
located shares above reproduce the logs to the third decimal. Differences: found-in-all-3 (the logs' pack-based counts
are 2 higher than the exact scorer's for every version, the differences between versions unchanged); v9g's module
sign test (15 up, 6 down in both; p 0.08 by the exact two-sided sign test here, 0.002 by the plan's test); the v2
pooled precision (0.228 here; EL's table gives per-run 0.200 / 0.244 / 0.246); screen D (not scored here: no complete
run). The costs are from stored usage at the list prices read on 2026-10-11 and agree with the logged spends where
both exist (v9j 5.91, v9k 6.00, v10 5.84).
