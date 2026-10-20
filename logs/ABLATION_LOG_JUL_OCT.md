# Ablation log, July to October 2026: the asset-generation prompt

How the prompt that replicates LAsset's asset generation (Algorithm 1 line 5) on NEORV32 changed from its first run in
July to the working version of 19 October. Four rounds: a recall round and a precision round in August (one call,
few-shot), a rebuilt prompt with a code-built relationship map in September, and a two-phase prompt in October. One
line per arm: what changed, the rule set before the run, the result, the decision. The reasoning behind each is in
the source logs named per round.

Every precision and recall figure below was re-derived on 2026-10-20 from the stored runs, by the script named in
each round's header. `results41.py`, `score_versions.py`, `score_lasset_exact.py` and the hand-arm scorer ran their
self-tests first; `score_august.py` has none, and its pooled figures agree with the logs' per-run means to within
0.004 for every family. A figure marked (log) comes from the source log and was not re-derived today: paired deltas
with intervals, oracle ceilings, judge readings, costs. Precision = share of listed elements that
the reference lists. Recall = share of reference entries listed. Unless a row says otherwise, figures are pooled over
the runs named, on the 15 tuning modules. Denominators: tuning 111 entries (109 findable under the exact scorer),
held-out 189 (187), all 41 modules 300 (296).

**Fixed across all four rounds.** Reference: LAsset's manual asset sheet, primary assets only. Closed set (the ports
and signals an asset may name) extracted by regex, never by the model; a listed name outside it does not score. No
numeric hint, no checklist of asset types and no identifier from the 41 modules in any prompt (the identifier ban
code-checked at import from August, the other two by code later). Three runs per version (five to promote in
August). A pass rule written before each run, with four logged exceptions (A-00, A-01, X-3, X-3R-8); the result pasted
from code.

| scorer | rounds | rule |
|---|---|---|
| strict (`src/eval_assets.py`) | 1, 2, 3 | a whole record matched to one of its fields, or the reverse, is a hit |
| exact (`experiments/03_two_phase_csa_pio/lab/analysis/.../compare_v8.py`) | 4 | names must be equal; only entries whose name is in the closed set are findable |

On LAsset's own lists the two scorers differ by less than 0.01 on every split (`map_pipeline/results41.py` against
`score_lasset_exact.py`, both run today). On ours the exact scorer is the harder test. The LAsset rows in the tables
come from those two scripts.

---

## Round 1. July prompt work, then the study of 2 to 8 August: recall (`logs/ABLATION_LOG.md`, short form `logs/RECALL_ABLATION_LOG.md`)

**Technique.** Few-shot, as LAsset: one call per module, gpt-5-mini at reasoning effort high, JSON reply. Few-shot
means the prompt carries worked examples of the task.

**Structure.** System prompt = core + example block. Core: INPUTS, DEFINITIONS, METHOD (step 1 conceptual assets by
P3164's four questions: confidentiality, integrity, availability, undermine; step 2 bind each to the elements that
store, carry, generate or gate it), RULES, OUTPUT CONTRACT. Only primary assets asked for. Example block: at v0,
P3164's own three analyses (8,460 chars); from v01, two worked input-reasoning-output cases from open IPs outside
NEORV32, `omsp_gpio` and `tiny_aes`, in the task's exact shape (97,049 chars).

**Inputs (user message).** (1) a datasheet summary from LAsset's SpecRAG (chunk 1,000, overlap 200, top 20,
ada-002); (2) the parsed ports and (3) the parsed signals as JSON, each with an LLM-written `function` string;
(4) the RTL with comments stripped. Shares over the 18 modules: 11.8 / 51.3 / 36.9% of the characters (log). Three of
the 18 modules have no reference entry and serve as negative controls.

**Strategy and guards.** Objective: recall, because LAsset's refinement stage only removes (its figures: precision
+0.083, recall -0.026). One change per arm, paired against its own baseline; `Expect:` and a decision rule in the log
before the run; paired bootstrap with modules as the pairing unit (an interval of about +-0.14 at 15 modules, so only
large effects resolve). From A-01 on, recall per element class (port, signal, signal field) is the primary reading,
because the aggregate hid two effects that cancelled. Two earlier failures set standing rules: a cap ("stop at ~20% of
the closed set") became a quota; a checklist of signal types became a generator.

**Results** (`map_pipeline/score_august.py`, strict, pooled over runs; listed = elements per run)

| version (arm) | change | rule before the run | P / R (runs) | listed | decision |
|---|---|---|---|---|---|
| v0 (A-00) | first prompt; P3164 rubric and its own examples | none: the noise floor | 0.300 / 0.553 (3) | 205 | base; recall sd 0.019 (log) |
| v01 (A-01) | two worked cases in the task's shape | port recall up; emissions up | 0.287 / 0.607 (3) | 235 | kept: port recall +0.18, signal recall -0.16, no module better (log); no labelled example IP has NEORV32's signal share, so the loss needs instruction |
| v01c2 (A-02) | "judge by role, not by location": ask of each concept which port carries it and which signal holds it | signal recall up and port holds: promote | 0.278 / 0.744 (5) | 297 | promoted: signal +0.106, port +0.262, aggregate +0.162 [+0.083, +0.232] (log); listed +29% at the 3 runs the decision used (235 to 304) |
| v01c3 (A-03) | a record-typed port is named whole, never a field | precision up, port recall >= 0.80, aggregate recall not down | 0.318 / 0.784 (5) | 274 | promoted on 3 runs (port recall 0.801; at 5 runs 0.796, under the floor by 0.004, the decision stands on the control's sign): port-field false positives 72.7 to 1.7 per run (log); a rename, not a removal (whole-port false positives 19 to 55); control v01r on the v0 core, same sign |
| v01c4, v01c5 (T-1) | step 1 written out as a concept list; the examples show it | diagnostic, not an arm: the output contract changes | 0.267 / 0.845, 0.284 / 0.849 (5) | 352, 331 | 82 to 85% of misses had a covering concept already (log): misses are binding failures; v01c4's empty concept lists were our cache line, not the model |
| v01c6 (A-08) | a closing sweep: re-read the closed set against each concept before moving on | union recall over 5 runs above 0.928 and recall up; stop clause: precision falls by more than 0.05 | 0.229 / 0.881 (5) | 428 | promoted: union 0.928 to 0.955, three entries no run had found; precision -0.038 (log), the next round's problem |
| v01c6p1 (P-1) | the datasheet summary removed, from the prompt and the examples | recall not down by more than 0.03 | 0.209 / 0.897 (5) | 476 | null, promoted: the summary did nothing |
| v01c6p1p2 (P-2) | the parsed lists removed; the model reads the declarations in the RTL | recall within 0.03 and listed down: the parsing stage is overhead | 0.243 / 0.886 (3) | 404 | promoted: 58% of the message gone; 187 names outside the parsed set, all real identifiers the regex missed, none invented; cost: union 0.950 to 0.937 (log) |
| v01c6p1p2d (L-1) | leaked names replaced (`ctrl_i`, a reference answer in 10 of 41 modules, was a naming example) | null expected | built, not run | | folded into v2; standing rule: no corpus identifier in a prompt |
| LAsset line 5, spec + RTL | | | 0.737 / 0.910 (1) | 137 | |

Recall came within 0.03 of LAsset's by listing three times as much. P-2' (keep the names, drop `function`) and P-3 (drop the RTL)
were registered and never run. Hand-off 8 August: objective switched to precision.

---

## Round 2. 8 to 18 August: precision with a recall guard (`logs/ABLATION_LOG_V2.md`)

**Baseline v2.** The P-2 prompt, RTL only, with three corrections: the text no longer refers to inputs that are not
sent (ungrounded names 187 to 106, log); the leaked names out; `clk_i` / `rstn_i` out of the clock-and-reset rule
(they stated a correct negative about 46 real elements). Each is a reversible function in `prompts_v2.py`, so every
earlier prompt hash still resolves.

**Guard, written before any run.** Precision is primary. Recall drop <= 0.03 against the arm's baseline passes;
0.03 to 0.06 means re-run at 5 runs; more than 0.06 rejects. Judged on the point estimate (an interval of about
+-0.14 would never fire). 3 runs to screen, 5 to promote. Hard checks on S-1, S-3 and SEC: named reference entries
that must survive whatever the aggregate does. From S-1 on, a null is recorded, not reworded and re-run. The guard is
a table-side rule, never a regenerate-until-better loop (that would select on the answers).

**Ceiling, measured before running.** Deleting every concept with no hit from the P-2 output, an oracle, gives
precision 0.362 (log). More than half the false positives sit inside concepts that also have a hit, so no concept-level
rule in a prompt reaches LAsset's 0.737.

**Results** (`map_pipeline/score_august.py`, strict, pooled over runs)

| version (arm) | change | rule before the run | P / R (runs) | listed | decision |
|---|---|---|---|---|---|
| v2 | baseline (above) | about the same as P-2 | 0.249 / 0.925 (3) | 413 | base; prediction wrong: precision +0.024, recall +0.033 (log); best available explanation the coherent binding text, but the delta bundles three corrections and is not attributable |
| v2s1 (S-1) | the container is not the content: a record is an asset only when what it holds is one | precision +0.02 to +0.05; 4 hard checks | 0.245 / 0.937 (3) | 425 | null, rejected: the carve-out ("entropy") fired on every TRNG field; listed +12 per run |
| v2r8 (R-8) | the A-08 sweep reverted | precision +0.04 to +0.06; recall drop <= 0.03 | 0.265 / 0.895 (5) | 375 | mechanism confirmed (largest concept 53 to 12 elements), precision null (log); the union ceiling did not fall; not promoted |
| v2x3 (X-3) | a third worked case, OpenTitan `gpio`, with matched negative examples | run without pre-registration; the standing guard only | 0.256 / 0.901 (3) | 391 | null; same dial as R-8 (elements per concept 4.47 to 4.15, log) |
| v2x3r8 | R-8 and X-3 together | additivity of the two | 0.296 / 0.853 (3) | 320 | first distinguishable precision gain, +0.025 [+0.013, +0.038] (log); guard fails (recall -0.072); cut the best-precision class (ports) hardest; rejected |
| v2s3 (S-3) | routed bus traffic belongs to the fabric; name the decision elements instead | precision +0.035 to +0.056; recall 0.000; 16 hard checks in three groups (traffic leaving the design, decisions in the bus module, 8 of the 17 control-record fields) | 0.249 / 0.943 (3) | 420 | rejected: the ban worked (bus module -19.7 listed per run, 0 recall cost); the "instead" added 27 signal and signal-field false positives across the 15 (log). Rule: prohibit without redirecting |
| v2sec (SEC) | LAsset's line 6: demote whatever only influences a primary to a secondary list | primary list must shrink and the departures reappear as secondary; recall drop <= 0.03; 28 hard checks | 0.283 / 0.628 (3) | 246 | rejected: 95% of departures reappeared (a destination moves, a prohibition adds), but the test "serves another element" is true of nearly every signal; 5 of 7 FSM-state entries lost, a conflict registered beforehand (SAIF calls FSM state secondary, the reference primary) |
| v2rp (RP) | the parsed list back, now with a role from a 152-label taxonomy, a relationship and an evidence line | recall and listed within +-0.03 / +-10%: the roles carry the coverage the sweep bought | 0.212 / 0.856 (3) | 449 | recall down; no decision logged; later attributed to RP's own status rule (a neutral label "does not stop one being an asset"), the example-block asymmetry unchecked; eight role names restated the rubric's answers |
| v2p3c1 (P3 + C1) | an open-vocabulary parse from occurrence profiles (every field cites the places the name appears); plus a block teaching the asset stage to read it | listed below v2p3 (its baseline, never run alone), recall within 0.03 | 0.239 / 0.847 (3) | 393 | no precision gain against v2; recall loss is instability, not blindness (union 0.955 to 0.945 with one entry lost, found-in-all-runs 0.882 to 0.727, log); 36.7 port-field false positives per run from the 929 spelled-out fields |
| LAsset line 5, RTL only | | | 0.680 / 0.748 (1) | 122 | |

Rejected before running: a blind per-concept cap (cap 4 on stored output: precision +0.022, recall -0.201, log).
E-3 (tighten "secret"), E-4 (a budget with a ranking rule), E-6 (record enumeration) registered, never run.

**Lessons that held from here on.** Every restrictive criterion added to this prompt raised emissions (S-1, S-3);
only a deletion (R-8) or an example change (X-3) lowered them. A population handed to the model gets named from
(the parsed list, a redirect, a carve-out); a destination (SEC) makes it move instead. More than half of the remaining false
positives are elements under correct concepts, and about half of all of them are elements LAsset lists as secondary.

---

## Round 3. 19 September to 3 October: rebuilt prompt, code-built map, citations (`logs/ABLATION_LOG_V2.md` section 10, `step1/lasset_step1/RELATION_EXPERIMENTS_LOG.md`, `assetgen_meta/prompt_opt/OPTIMIZATION_LOG.md`, `logs/TIMELINE.md`)

**Technique.** A meta model (gpt-6-astra) wrote both the method and the executor prompt (Step 1b, 19 Sep); the
executor is gpt-5-mini, later Claude agents and gpt-5.4. Few-shot again (two worked examples, `omsp_gpio` and
`tiny_aes`, now applying the prompt's own procedure). From 30 Sep the input carries a relationship map built from
occurrence profiles (every place a name appears, with its enclosing blocks and conditions): LLM-written in ismr,
code-built from ismc (1 Oct). From ist (1 Oct) the input also carries a flow graph, and every listed asset must cite
one occurrence ID and one map record, which code then checks. Structure moved from the LLM to code on 21 Sep after
the LLM profiler got 476 of 661 condition chains right before its validate pass (640 of 662 after).

**Structure** (`assetgen_meta/prompt_opt/v1/exec_prompt.txt`, 18,979 words): 1 what you are given; 2 what an asset
is; 3 purpose and use-case flows; 4 the flow graph; 5 established values; 6 roles along the path (sets, stores,
computes, exits); 7 never reported; 8 checks; 9 output; then the two worked examples.

**Inputs.** The RTL with line numbers and comments stripped; the map (one line per element, its occurrences, its
records); a flow graph of where each input's value goes. No datasheet summary.

**Strategy and guards.** Step 1b rule: a prompt counts only if its mean-of-3 precision is at least 0.03 above the
August baseline v2x3r8's (so 0.326) with recall >= 0.83; from 1 Oct the bar is 0.03 above the winner's (0.374). Hand
arms: each a named change on the winner, with a falsifier written first. Rules need
a basis outside the reference (`ASSET_DEFINITION.md`, 1 Oct); a rule supported only by reference counts may run as a
code filter after generation, as a labelled row. Held-out pre-registration (`HELDOUT_PREREG.md`): 18 files pinned by
hash, read once; adopt the code levers (MV majority vote over runs, NONE drop elements with no evidence path, BF add
back input pins) only if their precision gain over MV has a 95% interval above zero at recall >= 0.83. Optimization
loop (2 Oct): a version is kept only if its F1 beats the v0 mean by more than 0.03, or precision +0.03 at recall
>= 0.85; stop after two iterations under 0.02; a held-out check pre-registered before any held-out run of a loop version.

**Results** (strict; `assetgen_meta/hand_arms/score_hand_arm.py` for the hand arms, `map_pipeline/results41.py` for the
rest; mean of 3 runs on tuning unless noted)

| version | change | P / R | listed | decision |
|---|---|---|---|---|
| v2x3r8 (Aug) | the comparison row | 0.296 / 0.853 | 320 | |
| m7e194es0c, seed | the meta-written prompt | 0.379 / 0.787 | 230 | recall under the 0.83 floor; does not count. Half its precision lead over the baseline was reference conventions (log) |
| m7e194es0ism, winner | seed + the two worked examples | 0.344 / 0.847 | 273 | counts; the Step 1b winner. Held-out 0.352 / 0.852 |
| ismr | + the LLM-written relationship map in the input (ismc, the code-written map, scored the same: 0.346 / 0.787) | 0.353 / 0.778 | 245 | recall cost; map accuracy is not the lever |
| ismcap | + one "captured input" bullet | 0.355 / 0.829 | 259 | falsified: target inputs 4 of 12 |
| ismq | + the four P3164 questions per value, inside the call | 0.352 / 0.754 | 238 | harmful: answers uniform (integrity yes on nearly all, confidentiality no on all) |
| ismrq | map + questions | 0.360 / 0.697 | 215 | harmful |
| ismd | definition rules: deciders primary, transit registers secondary | 0.340 / 0.877 | 286 | not adopted: the transit rule used in 0 of 378 concepts; the fourth exclusion sentence that changed nothing |
| ist | eight-part restructure; occurrence ID and record cited per element | 0.359 / 0.691 | 214 | traceable (94% of citations verify, log) but recall fails |
| ist2 | ist without the in-call questions; a separate CIA labelling call | 0.343 / 0.733 | 237 | base of the optimization loop |
| loop v0 = ist2, Claude executor | | 0.335 / 0.887 (2 runs) | | base; run noise F1 0.027 (log) |
| loop v1, Claude | three edits from error patterns: a stored register needs a use record; no one-clock copies; inputs into unsupplied sub-units "set" | 0.371 / 0.934 | | kept (F1 +0.053 over the v0 mean); held-out 0.329 / 0.931 (1 run): precision +0.019 over v0, within noise (log) |
| loop v2, v3 | edit D withdrawn (no basis outside reference counts; moved to the evaluation layer as R1a, which then failed held-out: random thinning matched it in 24.8% of draws, log); no edit beat noise | not run | | loop stopped by its rule |
| final prompt (loop v1) on gpt-5.4 | the model, not the prompt | 0.406 / 0.820 | | held-out 0.388 / 0.877; all 41 0.394 / 0.856; the ist2 prompt on gpt-5.4 scored 0.407 on 2 complete runs (log), so the loop's edits add nothing measurable here |
| winner + MV + NONE + BF, held-out, gpt-5-mini | code levers after generation | 0.399 / 0.884 (log, pre-registered reading) | | adopted for gpt-5-mini (+0.049 over MV, interval above 0); on gpt-5.4 +0.011 with zero inside the interval (log), so the headline rows stay without levers |
| LAsset RTL only | | 0.680 / 0.748 tuning; 0.730 / 0.757 held-out; 0.711 / 0.753 all 41 | 122 | |

Nine versions built on the winner (ismr, ismc, ismcap, ismq, ismrq, ismd, ismp, ist, ist2) stayed between 0.336 and
0.360 precision on gpt-5-mini; six beat the winner's precision but fell under the recall floor. The map explained the false positives rather than
removing them: 97% of them cite an occurrence and record the map holds (log). On LAsset's own lists the map does not
separate hits from false positives either (AUC 0.639, interval down to 0.495, pre-registered, log).

---

## Round 4. 10 to 19 October: two-phase CSA to PIO prompt (`experiments/03_two_phase_csa_pio/lab/EXPERIMENT_LOG.md`, `HANDOVER.md`, `analysis/v10_diagnosis/DECISION_LOG.md`, one README per version under `experiments/03_two_phase_csa_pio/lab/prompts/`)

**Technique.** Prompt chaining, two calls per module. Phase 1 names the conceptual assets with the CSA rubric (the
four questions). Phase 2 walks each concept through a block diagram with P3164's PIO questions (points of influence
and observation) and labels each element primary or secondary; only primaries are scored. No worked examples:
definitions, a rubric and rules. Model gpt-5.6-luna at effort high, chosen after v1 ran once on three models (tuning,
exact, 1 run: gpt-5.4 0.187 / 0.771 at USD 27.35; gpt-5.4-mini 0.268 / 0.523 at 13.43; luna 0.183 / 0.807 at 0.77;
costs from stored usage, log).

**Structure.** System prompt = `common.md` (sent with both calls: 1 what you are given; 2 definitions 2.1 to 2.9:
objectives, flow, asset, conceptual, structural, primary, secondary, how the terms relate, points; 3 assume the
objectives; 4 indicators)
plus `phase1.md` (steps, then rules, then output) or `phase2.md` (walk, four questions per point, structural assets,
primary, secondary, rules, output). Words common / phase 1 / phase 2 (`wc -w`): v1 4,874 / 1,099 / 2,079; v9j
4,265 / 11,470 / 12,740; working version 4,265 / 11,729 / 12,830.

**Inputs.** `rtl.txt` (line-numbered), `closed_set.json` (every port, signal, record field with its tags), and
`diagram.txt`: a block diagram built by code (processes, generate blocks, concurrent assignments, instances; arrows that
carry a value or only decide, labelled with the elements they carry; clocks and resets kept apart), verified against
blind readers (368 of 368 facts) and ModelSim (549 of 549 blocks, 1,671 of 1,681 arrows). Phase 2 also gets Phase 1's
concept list.

**Strategy and guards.** Readings and falsifiers written in each version's README before the run; three runs for
adopted versions, judged on found-in-all-3 and element-level sign tests (Phase 2 alone varies by 0 to 5 hits per run
on the same Phase 1 input); r0 stop gates and single-run screens from v11 on. Through v8 a new rule enters only
after a blind boundary test on stored replies loses no correct find; from v9g on, after a rule-alone test on Claude
agents or on luna. Rules are tested alone (rule-isolation runs) before and after they enter; Phase 1 is measured alone by the share of
reference entries whose concept it located; Phase 2 alone by re-running it on stored Phase 1 replies. The full prompt
is never split into calls. Three decisions taken from the reference, not from theory, each logged as a user decision
with its reason and its check: clocks and resets are not conceptual assets (12 Oct); lines that only produced extra
concepts with no hit removed or restricted (12 Oct); exclusions for groups the reference never lists (stored-word
arrays and control-unit state, 18 Oct; debug-module registers, 19 Oct). From v9 on (14 Oct) 12 held-out modules
joined a second tuning set, tuning_v2, and from v9f on (17 Oct) the held-out 26 chose between versions, so held-out
figures from there are selection results.

**Results** (`experiments/03_two_phase_csa_pio/lab/analysis/score_versions.py`, exact, pooled over 3 runs unless noted; v10 to v12 had
their gates on tuning_v2)

| version | change | rule before the run | tuning P / R | held-out P / R | decision |
|---|---|---|---|---|---|
| v1 | the method as written, definitions from P3164, SA-EDI, SAIF, Nath & Tan | none: the first run | 0.179 / 0.804 | 0.239 / 0.822 | base; 392 to 422 false positives per run, most under extra concepts (Phase 1) |
| v2 | Phase 1 exclusions A1 to A6: clocks and resets, build-time values, pacing pulses, forwarded transactions, bus handshake copies, working values | falsified if the target clusters keep more than half of their v1 concepts, or structural recall below 0.780 in two of three runs | 0.228 / 0.786 | 0.244 / 0.779 | kept; the held-out drop is one module (xbus, forwarded transactions), fixed at v9 |
| v2a | v2, same meaning, shorter (common 4,874 to 4,057 words) | precision outside v2's run range | 0.210 / 0.798 | | shorter alone gave nothing |
| v3 | more specific Phase 1 steps at the same length | a merged bus-response concept reappears, or a hit drops below its v2 count | 0.235 / 0.841 | | kept: recall up, found-in-all-3 66 to 79 |
| v4 | bus request and response record ports and their fields are never primary | falsified if they stay primary | 0.295 / 0.826 | | kept |
| v4a | v4's content in v2a's wording | outside v4's run range | 0.300 / 0.832 | 0.275 / 0.788 | kept; r1 was the worst run in 8 of 9 modules at once (chance, p 0.022, log) |
| v5 | more exclusions (A, B, U rules) and 13 conflicts between rules fixed | precision above v4a's range in 2 of 3 runs; no all-3 hit of v4a found in fewer than 2 runs | 0.383 / 0.792 | 0.318 / 0.740 | kept on precision; held-out recall starts to fall (Phase 1 rules lose finds) |
| v5f | readable reply format: each key once, rows under their concept, primary or secondary as a label | the reply slip (a row losing its name) gone; precision and recall not down | 0.416 / 0.827 (6 runs) | | kept: slip 4 of 45 replies to 0; both up in every run |
| v5g | Phase 1 rules copied into Phase 2, which never reads Phase 1 | Phase 2 re-run on v5f's stored Phase 1: precision above the control in 2 of 3 pairs, recall not below in 2 or more, no all-3 element lost | 0.430 / 0.813 | | no real change: every run inside v5f's six-run range. A bar only in Phase 2 is ignored once Phase 1 built the concept |
| v6 | 24 paired rules (one copy per phase) from the v5g failure analysis; blind boundary test 0 hits lost, 246 false removed (upper bound) | precision above 0.500 in 2 of 3 runs; recall not below 0.780 in 2 or more | 0.620 / 0.780 | 0.426 / 0.652 | kept; losses from rules applied beyond their text |
| v6d | v6 condensed by 5% (three tracks a, b, c, one unit restored) | recall below 0.761 in 2 or more runs | 0.617 / 0.774 | | inside noise; named the condensed prompt (user, 13 Oct) |
| v7 | each rule's exceptions moved inside its main sentence (five narrowings) | at least 5 of the 10 lost entries back in 2 or more runs; recall not below 0.761; precision not below 0.601 | 0.614 / 0.817 | 0.375 / 0.697 | all readings held; named final (user, 13 Oct). Where an exception sits matters more than length |
| v8 | seven rules (B1, R1 to R6) from the v7 failure analysis | the targets in 2 or more runs; recall not below 86 of 109; precision not below 0.563 | 0.664 / 0.841 | 0.400 / 0.688 | kept |
| v9 | the forwarded-transactions rule narrowed: never a bus whose address the unit drives and whose acknowledge it takes on its own ports | xbus targets found in 2 or more runs; no tuning cost (bus, cache, cpu TP > 66, FP < 62); no reach into debug_dtm | 0.660 / 0.850 | 0.401 / 0.713 | kept; working version 14 to 18 Oct |
| v10 | the 17 hardest rules rewritten as blocks (scope, criteria, exceptions, outcome, evidence); one "reading a rule" sentence | V1: tuning_v2 precision and recall each not more than 0.02 under v9's | 0.647 / 0.826 | 0.403 / 0.679 | FAIL: tuning_v2 recall 0.739 to 0.709; V3 fails too (heldout_v2 precision 0.583 to 0.545) (log); each rule had passed alone |
| v11 | v10 + four fixes: two Phase 1 rule texts (forwarded transactions, access command fields) and two Phase 2 moves (operation selectors and the bus record-port bar to the end of step 4) | stop gate: tuning_v2 recall >= 0.694 on r0 | 0.676 / 0.844 (1 run) | 0.454 / 0.652 (1) | STOP: 137 of 206 = 0.665 (log); r1, r2 not sent |
| v12 | v11h (v10 + the two Phase 1 texts, v10's Phase 2) + three rule fixes that passed alone + the N12 bar on command-bit copies | gate on r0: tuning_v2 at least 144 of 206 correct and precision at least 0.404; heldout_v2 at least 69 of 90 and 0.530; 12 target entries | 0.611 / 0.807 (1) | 0.420 / 0.706 (1) | gate passed (146 of 206, 0.428), inside v10's run range; 1 of 12 targets recovered; N12 did not remove its false positives; v9 stays. Lesson: "not barred" alone does not predict recovery |
| v9f | v9 + five Phase 1 rule fixes | held-out recall: every run above 136 of 187 (v9: 134, 136, 130) | 0.667 / 0.862 (1) | 0.416 / 0.706 | no rise shown; v9 stays |
| v9g | v9f + five keep rules (N21 to N25) for groups the exclusions removed; port-buffers bar re-scoped | rise shown: every run above v9f's best run (138 of 187) | 0.687 / 0.844 (1) | 0.509 / 0.824 | rise shown; a candidate, never named; v9j named on 18 Oct |
| v9h | four more keep rules | a seven-module held-out cell first: each block's targets found in 2 of 3 runs; a change counts only if it holds in every run and moves 3 or more pooled finds; then all 41 | 0.617 / 0.872 (2) | 0.506 / 0.848 (2) | recall up, precision down; one keep rule dropped again |
| v9i | five bars for stable false positives | precision above both v9h runs on tuning_v2 and the held-out 26, recall not below the lower run by more than 0.02 (P1 to P3) | 0.660 / 0.872 (1) | 0.602 / 0.818 (1) | reading "not shown": precision up, held-out recall -0.03, one run |
| v9j | the control-unit bar spares the unit's ports; every keep block moved to the end of its step (order B; approximately, a build slip) | not more than 0.02 under v9g on tuning_v2; better than v9h on every group; J2 to J4 | 0.697 / 0.865 | 0.569 / 0.848 | working version 18 to 19 Oct; all 41 0.611 / 0.855 |
| v9k | a "walk-found internals" bar as the last bar of Phase 2 step 4 | tuning_v2 precision >= v9j + 0.05, recall not below -0.02 | 0.692 / 0.899 | 0.570 / 0.850 | FAIL: precision unchanged, rule not followed; all 41 0.611 / 0.868 |
| v9l | the same rule inside step 4's core sentence | the same | 0.694 / 0.865 | 0.569 / 0.827 | FAIL: followed, but the false positives moved to other elements |
| v9m | a code-built list of located elements as a Phase 2 input | the same | 0.682 / 0.832 | 0.540 / 0.831 | FAIL on both: followed exactly; the list became a menu |
| v9n_place | one primary per place where the information is (one sentence in Phase 2 step 4) | overnight screen on held-out r0 against v9j r0: recall >= 0.82, precision >= 0.58; then pooled over 3 runs: recall >= 0.848, precision > 0.569 | not run | 0.662 / 0.843 | the recall cut failed by 3 finds of 561; the user named it the working version anyway (19 Oct morning) |
| v9n_place_dbg | + the debug-register bar after the control-unit bar (Phase 1) and last (Phase 2) | three held-out runs: precision above 0.662, recall not below 0.843 by more than 0.02 | not run | 0.670 / 0.802 | bar fired (debug module 41 false fewer) but recall -0.04 elsewhere; not adopted |
| p1o_first | the debug-register bar as the FIRST Phase 1 block | Tier 1 (Phase 1 only; absent, first, after the control-unit bar, last, sham): located share within 0.01 of v9n_place (missed by one entry, 463 vs 469 of 561, p 0.49; the secondary rule "first or last holds the share where the middle does not" decided); Tier 3 (both phases): recall not below v9n_place's by more than 0.02, precision not below | 0.741 / 0.856 (run after the choice) | 0.689 / 0.838 | WORKING VERSION (user, 19 Oct); all 41 0.708 / 0.845 |
| LAsset RTL only (exact) | | | 0.672 / 0.752 | 0.724 / 0.759 | all 41 0.704 / 0.757 |

**Position and order** (Phase 1 only, held-out, share of reference entries located, 3 runs): the debug bar absent
0.836; first 0.825 (p 0.49); after the control-unit rule 0.807 (p 0.035); last 0.811 (p 0.011); sham text at the
same place 0.834 (log). Five orders of all 46 Phase 1 blocks: screened once, the two best confirmed over 3 runs at
0.829 and 0.832 against 0.825; inside noise, no order adopted (log).

**Wording and length** (tuning, exact): v2 to v2a shorter alone 0.228 / 0.786 to 0.210 / 0.798; v2 to v3 specific
at the same length 0.235 / 0.841; v6 to v6d condensed 0.617 / 0.774; v6d to v7 exceptions moved inside the sentence
0.614 / 0.817. Specific wording and the place of an exception moved the result; length alone did not.

**Remaining.** Internal registers under a right concept are the false positives left (v9j, all 41, 484 false
positives over 3 runs: 88% are internal registers or wires, 78% under a concept that also has a hit, log). The debug
module's reset-request output is never found when the bar is first. The rules under the three reference-convention
decisions (the 12 Oct restrictions, the v6 restrictions, the three bars of 18 and 19 Oct) rest on the reference, not
theory; three keep rules (N21, N23, N24) still need a logged decision. One model, three runs.

---

## Standing lessons, in the order they were learned

1. A number in a prompt becomes a quota; a list of types becomes a generator; a quoted real name is an answer (July,
   August). Enforced by code.
2. The aggregate hides effects that cancel; read per class (A-01).
3. A rule that renames does not remove (A-03). A rule that prohibits and then says what to name instead adds the
   substitute (S-3). A population shown to the model gets named from (the parsed list, RP, C1, v9m); a destination
   makes it move (SEC).
4. Re-check the premise that makes an arm impossible, not the reasoning built on it (P-2).
5. Where there is one right answer, code builds it (the closed set, the profiles, the map, the diagram).
6. A rule that passes alone can break inside the full prompt (v10), and a fix that passes alone need not recover
   its target (v12); a bar that exists only in Phase 2 is
   ignored once Phase 1 has built the concept (v5g); where an exception sits matters more than length (v7).
7. The position of one block changes the damage to the other rules from significant to none (p1o_first).
