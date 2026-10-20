# Precision study, 8 to 18 August 2026: ablation log, short form

The second prompt study of the LAsset replication (Algorithm 1 line 5, asset generation) on NEORV32. Objective:
precision, with recall as a guard. The full log is `logs/ABLATION_LOG_V2.md` (every Expect, Got and mechanism check); the companion
notebook `experiments/01_prompt_baselines/notebooks/precision_ablation_log.ipynb` re-scores every stored run, reads each arm's rule by code, and
regenerates a version on request. Every number below was re-derived from `runs/assets_tuning18_<version>_r<k>/` on
2026-10-20 with the strict scorer (`src/eval_assets.py`, metric M-2). Where today's number differs from the full log,
the row says so.

## Setup

**Question.** Can the asset prompt's precision be raised without losing recall? The recall study ended at
`v01c6p1p2`: 404 elements listed a run for 111 reference entries, precision 0.243, recall 0.886 (3 runs). LAsset's
initial list on the same 15 modules: 137 listed, precision 0.737, recall 0.910.

**Prompt technique.** Few-shot prompting, one call per module, gpt-5-mini at reasoning effort high, one JSON reply.
The system prompt is a fixed core (1,143 words) followed by two worked case studies from open IPs outside NEORV32,
`omsp_gpio` (openMSP430 GPIO) and `tiny_aes`, each as RTL, reasoning, output (8,018 words). Arm X-3 adds a third,
OpenTitan `gpio`, with worked rejections (12,014 words).

**Prompt structure** (`src/prompts_v2.py`, `ASSET_V2_BASE`, core sha `89efcccf1b55`; composed with the examples
`ea0608b316dc`, 70,262 characters):

1. INPUTS. The RTL is the closed set: every asset must bind to one name declared in it.
2. DEFINITIONS. Conceptual asset, structural (primary) asset, the P3164 conceptual-and-structural rubric
   (Confidentiality, Integrity, Availability, Undermine).
3. METHOD. STEP 1: the conceptual assets, written out first. STEP 2: bind each concept to elements, judged by role
   not location (A-02), record ports named whole (A-03), then one closing pass over the closed set per concept (A-08).
4. RULES. Clocks and resets are not assets; quoted names are illustrations; no name that was not read in the RTL.
5. OUTPUT CONTRACT. One JSON object: `ConceptualAssets`, then `Assets` (element, entity, objective, justification).

**Inputs.** The user message is the comment-stripped RTL and nothing else (the watchdog: 4,943 characters). No spec
summary, no parsed element list: P-1 and P-2 had shown both null for recall, and precision varies 2.5 times less in
this regime. Two arms put the parsed list back with an annotation per element (the watchdog's message: RP 18,591
characters; C1 30,709).

**Baseline `v2`** = the `v01c6p1p2` core plus three corrections, each a reversible function: D, the prompt no longer
refers to a parsed list that is not sent; L, four real NEORV32 names removed (`ctrl_i` is a reference answer in 10 of
the 41 modules, 9 of them held-out); N, `clk_i`, `rstn_i` and two P3164 names removed, quoted names declared
illustrative. Not an attributable delta against `v01c6p1p2`: three changes at once.

**Method and guard, fixed before any run** (full log, section 2):

- Precision is the metric. Recall is a guard, read at the results table and never inside generation: an arm whose mean
  recall drops more than 0.03 below its baseline does not become the baseline; 0.03 to 0.06 means re-run at five runs;
  more than 0.06 rejects. Judged on the point estimate. The paired recall interval is about ±0.14 at 15 modules and
  would never fire.
- Three runs to screen an arm, five to promote one. Paired bootstrap, modules as the unit, 95% interval, 10,000 draws.
  F1 reported second: it stays flat when an arm only lists less and rises when it removes false positives cleanly.
- Expect and a decision rule written before each run; Got pasted from code. Hard checks, named elements that must
  survive whatever the aggregate does. A null is recorded and not re-worded (set after S-1).
- Arm keys are alphanumeric (`v2s1`, never `v2_s1`): the run collector globs `_r*`, and a `_tag` key would be folded
  into the baseline's runs. No numbers in prompts. No name from the 41 modules (`prompts_v2.audit()` at import).

**What the queue could reach, measured before running** (section 6). Delete every concept with no hit from
`v01c6p1p2`'s own output, the best a concept-level rule could do: listed 404 → 272, precision 0.243 → 0.362, recall
unchanged. So 57% of the false positives sit inside concepts that also have a hit, and concept-level rules cap near
0.36.

**Rejected before running** (R-V2-01). A blind per-concept cap. Keep the first four elements the model wrote under
each concept: precision 0.243 → 0.265, recall 0.886 → 0.685. The model's order carries no ranking; a cap without a
ranking rule is closed.

## Results, every version

gpt-5-mini, 15 tuning modules, 111 reference entries, strict scorer. Mean over runs; paired deltas against `v2`
(modules as the unit, 95% interval; an interval that includes zero is a null at this sample size). "Drop" is the
guard's quantity, baseline recall minus arm recall.

| version (arm) | run | what changed | P / R (runs) | listed | paired dP | paired dR | drop, guard | decision |
|---|---|---|---|---|---|---|---|---|
| v2 | 8 Aug | corrections D, L, N on `v01c6p1p2` | 0.251 / 0.925 (3) | 413 | | | | base |
| v2s1 (S-1) | 10 Aug | a container is an asset only when what it holds is one | 0.246 / 0.937 (3) | 425 | −0.009 [−0.023, +0.006] | +0.010 [−0.010, +0.034] | −0.012, passes | null, rejected |
| v2r8 (R-8) | 10 Aug | the A-08 closing pass removed | 0.271 / 0.898 (3); 0.265 / 0.895 (5) | 368; 375 | +0.005 [−0.011, +0.019] | −0.019 [−0.044, +0.009] | 0.027 at 3 runs, passes; 0.029 at 5 | null, not promoted; kept for the combination |
| v2x3 (X-3) | 10 Aug | third case study with worked rejections | 0.259 / 0.901 (3) | 391 | −0.005 [−0.024, +0.012] | −0.016 [−0.049, +0.016] | 0.024, passes | null, not promoted |
| v2x3r8 (X-3R-8) | 10 Aug | R-8 core + X-3 examples | 0.296 / 0.853 (3) | 320 | +0.025 [+0.013, +0.038] | −0.054 [−0.096, −0.016] | 0.072, FAILS | rejected |
| v2s3 (S-3) | 11 Aug | routed traffic belongs to the fabric; name the decision elements instead | 0.249 / 0.943 (3) | 420 | −0.016 [−0.036, −0.001] | +0.017 [+0.000, +0.039] | −0.018, passes | rejected: precision down |
| v2sec (SEC) | 11 Aug | STEP 3: SAIF's demotion test, a secondary array per primary | 0.287 / 0.628 (3) | 246 | +0.069 [+0.006, +0.131] | −0.300 [−0.379, −0.220] | 0.297, FAILS | rejected |
| v2rp (RP) | 17 Aug | the parsed list back, with a role from a 152-label taxonomy, a relationship, an evidence line | 0.213 / 0.856 (3) | 449 | −0.054 [−0.084, −0.028] | −0.055 [−0.100, −0.018] | 0.069, FAILS | rejected |
| v2p3 (P3) | not run | the open-vocabulary v3 parse instead of the taxonomy | | | | | | built only |
| v2p3c1 (C1) | 17 Aug | P3 plus a block that teaches the asset stage to read the annotations | 0.240 / 0.847 (3) | 393 | −0.038 [−0.071, −0.005] | −0.057 [−0.104, −0.011] | 0.078, FAILS | rejected |
| LAsset initial, spec + RTL | | | 0.737 / 0.910 | 137 | | | | |
| LAsset initial, RTL only (the like-for-like row) | | | 0.680 / 0.748 | 122 | | | | |

No arm was promoted. The baseline stayed `v2` for the whole study. Today's scorer gives C1 0.240 / 0.847 and RP
0.213 / 0.856; the full log recorded 0.249 / 0.848 and 0.210 / 0.855 (later scorer changes; see the notes at the end).

## The arms, in order

### v2, the baseline (run 8 Aug)

- Expect: about `v01c6p1p2` (P 0.243, R 0.886); the de-leak may cost up to 0.009 recall.
- Got: P 0.251, R 0.925. Paired against `v01c6p1p2`: precision +0.024 [+0.007, +0.042], recall +0.033
  [+0.002, +0.073]. The prediction was wrong in direction. Names not in the closed set fell 187 → 106 over three runs
  (correction D: the binding instruction had pointed at a list that was not sent). `clk_i` and `rstn_i` without their
  example cost about 1.7 false positives a run. Listed went up, 404 → 413: precision rose by adding hits, not by
  removing extras.
- Where the error is (section 5b): 33% of false positives are many distinct fields of one record, each listed once
  (`uart` `ctrl`: 12 fields listed, 3 are assets); groups of five or more fields hold 369 listings, 56 hits. The
  largest concept binds 53 elements (`neorv32_bus`), up from 15 in the recall study. `neorv32_bus` alone is 19% of all
  false positives.
- Next: S-1, the cheapest rule aimed at the wrong-record group.

### S-1, container versus content (`v2s1`, built 9 Aug, run 10 Aug)

- Change: one RULES bullet. A structure that stores or carries data is an asset only when what it holds is itself an
  asset (a secret, a credential, entropy, privileged configuration). Basis: SA-EDI types the content, never the vessel;
  P3164 3.1.2 asks for the RTL that produces, stores and transports a conceptual asset.
- Target, measured on `v2`: 225 of 930 false positives are fields of a record that holds no reference asset. Ceiling
  listed 413 → 338, precision 0.251 → 0.304.
- Expect: precision +0.02 to +0.05, recall −0.01 to −0.02. Rule: precision up and guard passes → promote at five runs;
  precision null → record and move on, do not re-word. Hard checks: `trng` `fifo.avail`, `fifo.free`, `fifo.re` and
  `cpu_cp_cfu` `key_mem` must survive.
- Got: null. Precision −0.009 [−0.023, +0.006]; recall 0.937, the highest so far; listed +12. Hard checks all
  survived. The target group did not move (wrong-record fields 75.0 → 76.0 a run); the growth was in plain names.
  Mechanism: in the TRNG everything holds entropy, so the carve-out fired everywhere (listed 14.0 → 20.0 a run, six
  new buffer-field false positives). Elements per concept rose 4.47 → 4.64 while concepts per module stayed flat.
- Decision: rejected. Rule recorded: a null is not re-worded and re-run; a security-flavoured carve-out becomes a
  licence in the security-relevant modules. Hypothesis for R-8: the A-08 closing pass cancels restrictive rules.
- Next: R-8.

### R-8, revert the A-08 closing pass (`v2r8`, run 10 Aug)

- Change: the two "close each concept" paragraphs deleted; nothing added. The only arm that removes, so nothing
  design-specific can leak through it. When the pass was added in the recall study it took listed 331 → 428 and
  precision 0.285 → 0.229 for recall +0.032.
- Expect: precision +0.04 to +0.06, recall −0.02 to −0.04, listed −20%. Guard arithmetic written first: a symmetric
  revert lands near 0.893, inside the indeterminate band, so promotion needs five runs whatever the point estimate.
  Registered cost: the union-over-runs ceiling, which only A-08 ever moved.
- Got: precision null, mechanism confirmed. Three runs: P 0.271, R 0.898, precision +0.005 [−0.011, +0.019], recall
  −0.019 [−0.044, +0.009], drop 0.027. Five runs: P 0.265, R 0.895, drop 0.029, on the floor. Elements per concept
  4.47 → 3.76, the largest concept 53 → 12, concepts per module 6.16 → 6.53: the model conceived as much and bound
  less. The union ceiling did not move (0.955 both). Signal recall alone fell, −0.025 [−0.050, −0.005].
- Decision: not promoted (precision null) and not rejected: the one edit with a measured handle on fan-out.
- Next: X-3, then the two together.

### X-3, a third worked example (`v2x3`, run 10 Aug; not pre-registered)

- Change: only the examples move. OpenTitan `gpio`, chosen from the 21 golden lists in LAsset's repository as the one
  IP where internal-signal assets dominate (3 of 5), with explicit rejections. The core is byte-identical to `v2`.
- No Expect and no rule were written before the run, which the full log states; judged against the standing guard
  only.
- Got: null. P 0.259, R 0.901; precision −0.005 [−0.024, +0.012]; drop 0.024, passes. Pooled precision rose and
  paired precision fell: the losers lost more than the winners gained; the paired number is the one reported. Three
  quarters of the recall loss is `neorv32_bus`, two fields of the `keeper` record. A causal claim that blamed one
  sentence of the example was withdrawn when a `v2r8` run without that sentence showed the same pattern. Elements per
  concept 4.47 → 4.15: the same dial as R-8, about 40% of the distance, not an independent proposition.
- Decision: not promoted.

### X-3R-8, the combination (`v2x3r8`, run 10 Aug; not pre-registered)

- Change: the R-8 core with the X-3 examples. The one prediction the design implies is additivity.
- Got: the first distinguishable precision gain, and the guard fails. P 0.296, R 0.853, listed 320. Precision +0.025
  [+0.013, +0.038], 12 modules better and 1 worse; F1 +0.023 [+0.008, +0.038]; recall −0.054 [−0.096, −0.016];
  aggregate drop 0.072, more than 0.06. Not additive: precision 0.296 against an additive 0.279, recall 0.853 against
  0.874; the two edits turn the same dial (elements per concept 3.54, largest concept 20).
- Where it cut: port recall −0.120 [−0.202, −0.043], the only class that moved; signal and signal-field null. Listings
  cut by class: ports −31% (precision 0.286 in `v2`), signals −18% (0.307), signal fields −17% (0.180). The pruning
  cut hardest into the best class and least into the one carrying most false positives. It is selective (95 hits kept
  against 80 expected from random pruning at the same volume), but class-blind. First arm to lower the union ceiling,
  0.955 → 0.928.
- Decision: rejected on the guard. Reading: the next arm must be class-aware and selective, not volumetric.
- Next: S-3.

### S-3, routed traffic belongs to the fabric (`v2s3`, built and run 11 Aug)

- Change: one RULES bullet. Traffic the module forwards unchanged is not its asset; judge it in the module whose
  function is the interconnect; name the decision elements instead. Exceptions keyed on checkable facts: the record the
  module acts on, and traffic that changes representation or leaves the design. Basis: LAsset p.2 (buses and ports that
  carry a primary's data are secondary), SA-EDI. Supersedes E-1, which was a name list.
- Headroom on `v2`: elements declared with the shared interconnect record type are 76.0 false positives a run (25% of
  all) at zero hits; the same test on the control record would cost 0.150 recall, so the rule is a criterion with a
  boundary, not a blocklist. Built on `v2`, not on R-8, to keep one proposition.
- Expect: precision +0.035 to +0.056, recall 0.000 to −0.010, listed −60 to −80 a run, elements per concept unchanged.
  Rule: precision up and guard and all hard checks → promote at five runs; any hard check fails → reject; null →
  record, do not re-word. Hard checks: traffic leaving the design (`uart_rxd_i`, `uart_txd_o`, `spi_dat_i`,
  `twi_sda_i`); decisions inside the bus module (`sel`, `stb`, `port_sel`, `state`); the 17 control-record reference
  assets (`ctrl.enable`, `ctrl.lock`, and so on). Mechanism check: if elements per concept moves more than precision,
  it is the fan-out dial again.
- Got: rejected, precision moved the wrong way. P 0.249, R 0.943 (the highest of the study); precision −0.016
  [−0.036, −0.001]; listed +7.7 a run. Three of four predictions wrong. What worked: fabric-typed false positives
  76.0 → 55.7 a run, 19 of the 20 in `neorv32_bus`, with no recall lost there; the control-record boundary held, 0
  missed of 51 entry-runs; elements per concept 4.41, so not the fan-out dial. One hard check failed: `bus` `stb`
  3 of 3 → 2 of 3. Why precision fell: the redirect ("name the decision elements instead") fired where nothing was
  forwarded. Port listings −22, signal +11, signal-field +16 a run; the TRNG, which forwards no bus traffic, listed
  76% more.
- Decision: rejected. Rule recorded: prohibit without redirecting. Two for two, every restrictive rule added to this
  prompt raised listings (S-1 +12, S-3 +8); only a deletion (R-8, −45) and an example change (X-3, −21) lowered them.
- Next: SEC, a destination instead of a prohibition.

### SEC, a secondary list (`v2sec`, built and run 11 Aug)

- Change: STEP 3, SAIF's primary/secondary definition with its two worked examples and a demotion test; one contract
  field, a `secondary` array per primary. The first arm on Algorithm 1 line 6. Scoring unchanged (the scorer reads
  `Assets` only; verified by injecting secondary arrays into a `v2` run and re-scoring).
- Headroom, with LAsset's own secondary lists as the oracle: elements that are only ever secondary are 133 false
  positives a run against 4 hits (33 to 1); demoting them gives precision 0.249 → 0.358, recall −0.036. A registered
  conflict: SAIF calls FSM state secondary; the reference lists 7 such elements as primary.
- Expect: precision +0.05 to +0.11, recall −0.010 to −0.036, listed −80 to −133 a run. Rule: the mechanism check
  decides first: if the primary list did not shrink, or fewer than half the departures reappear as secondary, reject.
  Then precision up and drop ≤ 0.03 and hard checks → promote; 0.03 to 0.06 → five runs (expected: the arm sits on the
  guard by design). Hard checks: the 17 control-record assets, the four boundary ports, the 7 FSM elements.
- Got: rejected on the guard; the mechanism check passed. P 0.287, R 0.628; precision +0.069 [+0.006, +0.131], the
  largest gain of the study; recall −0.300 [−0.379, −0.220], 0 modules better, 14 worse; F1 flat. 123 distinct
  elements left the primary list and 117 (95%) reappeared as secondary: a destination moves elements where a
  prohibition added them. Elements per concept 4.47 → 2.69 at the same concepts per module. The demotion test has no
  floor: in RTL nearly every element "serves" another, so it selected on nothing (4 false positives removed per hit
  lost; the oracle 33). All three hard-check groups failed: control record 9 of 51 entry-runs missing, boundary 3 of
  12, FSM state 10 of 18. The registered conflict materialised: `bus` `state`, `sel`, `stb`, `hwspinlock` `sel`, `wdt`
  `cnt` demoted. 17 to 33 elements a run were both primary and secondary, against the contract.
- Decision: rejected. The successor the log names, SEC's destination with S-3's type-scoped population, was not built.
- Next: RP, the input side.

### RP, the parsed list back with roles (`v2rp`, registered 16 Aug, run 17 Aug)

- Change: the first arm on the input, not the text. Correction D undone; the parsed ports and signals return,
  annotated by a new line-4 parser (`src/prompts_parse_v2.py`) with a role from a 152-label taxonomy, a relationship
  and a line of RTL evidence. One new RULES bullet: annotations are evidence, never verdicts, in both directions. The
  closed set is copied from the cached parse and asserted identical, so the scorer is untouched. The examples still
  reason from RTL alone, a registered asymmetry.
- Why: recall in this prompt is bought with text that raises listings (A-08). If the list carries that coverage, the
  text becomes removable. A substitution test with three readings: flat recall and listings → the roles carry the
  coverage, run R-8 on `v2rp` next; recall and listings up → a second generator; recall down → the list displaces the
  reading of the RTL.
- Gate before the run: share of the closed set with a positive lead role (reference asset rate 7.2%). Measured
  afterwards: 10.6%, so the gate would have passed.
- Expect: listed within ±10% of `v2`, recall within ±0.03. A null is a real result.
- Got: recall down. P 0.213, R 0.856, listed 449 (+36); precision −0.054 [−0.084, −0.028], recall −0.055
  [−0.100, −0.018]; port recall −0.115 [−0.215, −0.022]. 11 port-field false positives a run (zero under every
  RTL-only arm; the list spells out the fields). Names not in the closed set: 0.
- Decision: rejected: the list displaces RTL reading. And eight of the taxonomy's role names restate STEP 1's own
  rubric (`A1_KEY_MATERIAL`, `A2_ENTROPY_SOURCE`, `F3_OVERRIDE_OR_BYPASS`): the parser fills in the answer sheet.
- Next: P3, the vocabulary dropped.

### P3 and C1, the open-vocabulary parse and how to read it (`v2p3` built; `v2p3c1` run 17 Aug)

- P3: the same input regime, a different annotation (`src/prompts_parse_v3.py`): `function`, `functionality`, `role`
  (open prose), `relationship`, `evidence`, with no vocabulary; every field must derive from an occurrence profile, the
  list of places the name appears; verdict words refused on the output by code; one entity's source per call, comment
  stripped; the two line-4 parsers merged into one call (a registered deviation, 61 → 30 calls). Same Expect and rule
  as RP; against RP, if the two land together the vocabulary never mattered. Built as a separate version so RP's three
  paid runs keep their sha. Never run on its own.
- C1: one addition to P3, a READING THE ANNOTATIONS block before STEP 1: read `evidence` first, which field bears on
  which rubric question, what may not be inferred, and "a coupling is not a reason". No asset criteria added. The two
  patterns that separate reference assets in the parse (appears in a condition: 80% of true dotted-signal assets
  against 28%; written from an input port: 57% against 24%) are deliberately not in the prompt.
- Expect (C1): listed below P3, recall within ±0.03. Rule: listed down with recall flat → the reading procedure was
  what was missing; flat → the model already read the fields; up → the list is a generator whatever is said.
- Got (C1): P 0.240, R 0.847, listed 393; precision −0.038 [−0.071, −0.005], recall −0.057 [−0.104, −0.011],
  drop 0.078. Against RP a clear win (listed −56, precision +0.027). Against `v2` no precision gain and recall down.
  52 port-field false positives a run (the full log: 36.7), from the 929 spelled-out field names; no reference lists
  a port field. The recall loss is instability, not blindness: reference entries found in every run, `v2` 97 of 106
  reachable, C1 83 of 103.
- Decision: rejected. The fix the log names is to stop sending the fields, not to re-word A-03. The parser itself
  went through three generations (edges 3,017 / 2,392 / 2,464; a rule that named a target population became a quota
  and was reverted). The occurrence profile is the seed of the second study.

### Registered, never run

- E-1, replicated interconnect is not an asset: superseded by S-3 (its name list was the wrong instrument).
- E-2, revert A-08: became R-8.
- E-3, tighten what qualifies as a secret: headroom shrank from +0.034 to +0.019 after `v2` ran; a pure relabelling is
  invisible to the metric; not run.
- E-4, per-concept budget with a ranking criterion: between the blind line (P 0.265, R 0.685) and the oracle line
  (0.334, 0.862) at cap 4; a number in a prompt, so last; not run.
- E-5, port-field decay: a scoring-side check first; not run.
- E-6, record enumeration guard: the largest measured lever (groups of five or more fields: 313 false positives, 56
  hits); no mechanism found that separates the fields without a cap or a ban; closed.

## Where the study stopped

- Closed 18 August (commit `9dc383d`). No arm passed its rule. The best precision, `v2x3r8` at 0.296, failed the
  guard; the best recall, `v2s3` at 0.943, lost precision. Precision moved only with a class-blind dial that trades
  hits and false positives together, and the concept-level oracle caps that route near 0.36.
- The precision line continued in September with a prompt rebuilt from scratch on the same rubric, RTL only,
  gpt-5-mini: P 0.344, R 0.847 (`v2x3r8` served as its reference row, with its own recall floor of 0.83). Then the
  occurrence profile and relation map became the second study.
- Rules carried forward: a null is not re-worded; prohibit without redirecting; a destination moves elements, a
  prohibition adds them; a rule that names a population makes a quota; a quoted real name is an answer; no number in a
  prompt. Three are now enforced in code.

## Verification notes (2026-10-20)

- Every run folder's stamped prompt sha matches the prompt recomposed from `src/prompts_v2.py` and the two example
  modules, for all nine run versions. `v2p3` has no run folder.
- Means, paired deltas, guard verdicts, hard checks, fan-out numbers, the SEC movement test (123 left, 117 back as
  secondary), the concept oracle (0.362) and the cap sweep all reproduce the full log to the third decimal. Union-over-
  runs recall for `v2` is 0.955 today; the full log gives 0.946 under R-8 and 0.955 under C1.
- Scorer drift since August: C1 reads 0.240 / 0.847 and 52 port-field false positives (log: 0.249 / 0.848, 36.7); RP
  0.213 / 0.856 (log: 0.210 / 0.855). The full log's C1 table also gives `v2` as 0.250 / 0.930 against 0.251 / 0.925
  in its own section 5.
- The `v2p3c1` run metadata records parse fingerprint `540765753f`, the content of `parsed_v3_tuning18/` today,
  which the full log's parser table labels gen3; the log's C1 result line says gen2 (`450d8de774ca`, now in
  `parsed_v3_tuning18_gen2/`). The metadata is the primary record.
