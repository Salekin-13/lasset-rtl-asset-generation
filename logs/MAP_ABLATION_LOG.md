# The map study, 20 September to 3 October 2026: ablation log, short form

The third study of the LAsset replication (Algorithm 1 line 5, asset generation) on NEORV32. Question, written on
2026-09-18 before any run: does a code-built occurrence profile and relationship map raise the precision of the LLM's
asset list without losing recall? The first two studies had reached LAsset's recall by listing three times as much
(`logs/RECALL_ABLATION_LOG.md`, `logs/ABLATION_LOG_V2.md`); the August attempt to give the LLM an LLM-written
annotated list had made things worse (v2p3c1: precision 0.251 to 0.240, recall 0.925 to 0.847). The full record, with
every reading as written before each run, is `step1/lasset_step1/RELATION_EXPERIMENTS_LOG.md` (REL),
`experiments/02_rtl_structural_analysis/notebooks/assetgen_meta.ipynb` (NB-meta, markdown cells 18 to 67), `assetgen_meta/HELDOUT_PREREG.md` (HPR),
`assetgen_meta/prompt_opt/OPTIMIZATION_LOG.md` (OPT) and `assetgen_meta/contribution_assessment/1_evidence_ledger.md`
(LED). The structures' own build log is NB-meta cells 70 to 85 and `experiments/02_rtl_structural_analysis/notebooks/lasset_step1.ipynb`.

Every number below was re-derived on 2026-10-20 from the stored runs (`runs/`, local, not published) by
`experiments/02_rtl_structural_analysis/notebooks/map_ablation_log.ipynb`, with the strict scorer (`src/eval_assets.py`), unless marked with a source key: those
figures come from the log named and were not re-derived (LLM-stage counts whose inputs are not in this notebook).
Precision = hits / listed elements; recall = hits / reference entries. Tuning set 15 modules, 111 entries; held-out set
26 modules, 189 entries. Paired deltas pair the modules, with a 95% bootstrap interval; an interval that includes zero
is a null at this sample size. Run-to-run noise is about 0.03 in both precision and recall; a change under that is not
a result.

## Prompt technique and structure

- **Technique.** A procedure prompt with two worked examples (few-shot, as LAsset does), one call per module, gpt-5-mini
  at reasoning effort `high`, JSON output. From 30 September the module's relationship map, built by code, is added to
  the input as grounding: the model is told the map is an index to the RTL, never a candidate list. From 1 October the
  model must cite, for every listed element, one occurrence ID and one relationship record that holds there, and code
  checks the citation. From 2 October the four security questions (confidentiality, integrity, availability,
  undermined behaviour) move to a separate labelling call, and the final version moves to gpt-5.4.
- **Baseline prompt `m7e194es0ism`** (sha `0d0def4c6fe3`, 103,678 chars): a seed written by a meta model (gpt-6-astra)
  from IEEE P3164's conceptual-then-structural method, 26,639 chars (DEFINITIONS: two axes, conceptual and structural
  asset, primary and secondary, transport, sub-block connection field, closed set, evidence levels; sections 1 to 11:
  information, observation, use-case flows, external information, asset definition, security relevance, evidence
  sufficiency, uncertainty, analysis procedure, validation, output; the output schema), then two worked examples that
  apply the seed's own procedure to `omsp_gpio` (14 verified assets) and `tiny_aes` (4), 77,037 chars. Its own
  provenance (Step 1b, 19 to 21 September: six meta-prompt screens, then three hand rounds; counts only at recall 0.83
  or more and precision up by 0.03) is NB-meta cells 0 to 17 and `logs/ABLATION_LOG_V2.md` section 10. This log takes
  it as given.
- **Map arms `ismr` / `ismc`** (114,084 chars): the seed, then a 10,404-char section that tells the model how to read
  the map through the four P3164 questions and how to tell a copy relay, a decision-chain input, a record-field
  fan-out and a reset or clock driver from the element that realises the concept, then the examples. Input: the
  comment-stripped RTL, then `=== RELATIONSHIP MAP ===`, a compact view of the module's map with occurrence IDs turned
  into line numbers.
- **Traced prompts `ist` (193,492 chars), `ist2` (178,439) and the final `prompt_opt/v1` (180,670 chars, about 19,000
  words)**: nine sections (1 what you are given, 2 what an asset is, 3 purpose and use-case flows, 4 the flow graph,
  5 established values, 6 roles along the path: sets, stores, computes, exit port, 7 never reported, 8 checks, 9 output:
  one occurrence ID and one record per asset) and the same two examples with map excerpts whose IDs code computed.
- **Inputs of the traced arms** (`assetgen_meta/traced_inputs_v2/<split>/<module>.txt`, written by code): the RTL with
  comments removed and each line numbered by its source line; the relationship map, one `PORT` or `SIGNAL` line per
  element with its occurrences, connections and typed records (`CARRIES`, `GATES`, `SELECTS`, `CLOCKED_BY`, ...), each
  record tied to the occurrence IDs where it holds; and a flow graph computed from the records. Watchdog: 32,592 chars
  (RTL 5,826, map 23,890, flow graph 2,845) against 4,943 for the RTL-only message; over the 15 tuning modules 943,179
  chars, 6.4 times the RTL-only messages (RTL 18.6%, map 74.6%, flow graph 6.8%).
- **The two structures.** Occurrence profile: every place a name appears, with ID, line, context chain, path condition
  and a SITE tag (what the name does there). Relationship map: typed records between elements, each at an occurrence.
  Structure and inventory by code (tree-sitter); SITE tags by the v3d LLM profiler on the tuning modules and by a code
  tagger on held-out (agrees with the profiler on 5,734 of 5,760 tuning rows, REL); records by `step1/code_pairs_v2.py`,
  frozen sha `b0e767000ec2`. Against the gold sample (120 occurrences, 212 records, written by gpt-6-astra, tuning
  modules only): typed precision 0.988 and recall 0.988, 95% interval 0.969 to 1.0; 210 right, 2 wrong, 2 missed.
- **Scoring.** Strict scorer, primary assets only, mean of 3 runs. External rows: LAsset's initial lists, spec+RTL
  (tuning 0.737 / 0.910, 137 listed; held-out 0.734 / 0.862, 222) and RTL-only (0.680 / 0.748, 122; 0.730 / 0.757,
  196), the like-for-like row. The Step 1b bar for adopting an arm: precision 0.374 or more at recall 0.83 or more.

## Fixed before the study

- **Code where there is one right answer.** The LLM profiler's second pass got the enclosing `if` / `case` structure
  right for 476 of 661 occurrences and 640 of 662 after a checking pass (run 6, NB-meta cell 70); structure moved to
  code (v3, 0 wrong). Batches capped at 85 occurrences after one 168-occurrence batch lost 11 rows (v3b). Three rounds of
  tag-rule edits cut code-flagged entries from 26 to 3 of 2,142; the same prompt run twice changes 44 of 2,117 entries
  (2.1%), the noise floor (`experiments/02_rtl_structural_analysis/notebooks/lasset_step1.ipynb`).
- **Code writes the relationships** (settled 2026-09-30, REL). LLM annotator E0: 68.4% of the code reference's
  mirrored typed pairs; an identical re-run moved it 2.0 points (E1); linked batches lost 8.1 (E2); a pair-first prompt
  gained 4.3 (E3); a repair pass lost 13.8 (E4, rejected). Blind adjudication of disagreements: code right about 66.5%,
  LLM 28.3%. On the gold sample E3 beat the then-current code on precision, so the question was reopened, a six-fix
  code writer was frozen before scoring, and it won: recall +0.083 [+0.053, +0.113] over E3, precision level.
- **Step 1b bar and recall floor** carried from the prompt rebuild: adopt only at P >= 0.374 and R >= 0.83.
- **Held-out set obtained 2026-09-21** (26 reference modules never used in tuning). Pre-registrations pin files by sha
  and are read once (HPR; `prompt_opt/HELDOUT_CHECK_PREREG.md`; `lasset_layer/PREREG.md`).
- **Rules need a basis outside the reference** (`assetgen_meta/ASSET_DEFINITION.md`, 2026-10-01): a rule supported only
  by a count from the reference runs as code after generation and is reported as its own row, never as a prompt line.
- Standing from the earlier studies, enforced by code: no corpus identifier, no numeric emission hint, no banned word
  in a prompt; every version writes to its own run folders; pass rule before the run, result pasted from code.

## Results

| arm | change | P / R (runs) | listed | decision |
|---|---|---|---|---|
| `m7e194es0ism` | baseline, RTL only (20 Sep) | 0.344 / 0.847 (3) | 273 | base; the Step 1b winner |
| Step 2 | six frozen code rules over the LLM map, after generation (21 Sep) | 0.433 / 0.802 | 206 | fail: +0.089 P, -0.045 R against +0.10 and -0.03 |
| `ismr` | + map section, LLM-written map (30 Sep) | 0.353 / 0.778 (3) | 245 | fail: below the recall floor |
| `ismc` | + the same section, code-written map (1 Oct) | 0.346 / 0.787 (3) | 252 | fail; equal to `ismr` within noise |
| `ismcap` | + one bullet, captured input = setting point | 0.355 / 0.829 (3) | 259 | falsified: targets 4 of 12 |
| `ismq` | + four questions per value, required negative | 0.352 / 0.754 (3) | 238 | harmful: recall -0.093 |
| `ismrq` | `ismr` + the same questions | 0.360 / 0.697 (3) | 215 | harmful: recall -0.081 |
| `ismd` | definition rules (deciders primary, transit secondary) | 0.340 / 0.877 (3) | 286 | not adopted: transit rule not followed |
| held-out, `ism` | the baseline on the 26 unseen modules (pre-registered) | 0.352 / 0.852 (3) | 458 | descriptive |
| held-out, MV+NONE+BF | code levers after generation | 0.399 / 0.884 (vote) | 419 | pass: +0.049 [+0.025, +0.080] over MV; adopted |
| held-out, GUARD | drop record fields never read in a condition | 0.446 / 0.801 (3) | 340 | secondary row only (reference-derived) |
| `ist` | traced restructure: citation per element, questions, side lists | 0.359 / 0.691 (3) | 214 | citations pass (0.812); recall fail |
| `ist2` | `ist` minus questions and side lists; CIA in a second call | 0.343 / 0.733 (3) | 237 | fail: verified 0.818 < 0.90, R < 0.817 |
| opt v0 / v1 (Claude) | the `ist2` prompt; + edits A, B, C | 0.335 / 0.887 (2); 0.371 / 0.934 (3) | 294; 279 | v1 kept: F1 +0.045 over v0 |
| opt v1, held-out (Claude) | one pre-registered run each | v0 0.310 / 0.899; v1 0.329 / 0.931 | 548; 535 | direction only: dP +0.019 |
| `ist2` on gpt-5.4 | paired baseline for the final | 0.407 / 0.815 (2 complete) | 223 | |
| final on gpt-5.4 | opt v1 on gpt-5.4 (2 Oct) | 0.407 / 0.820 (3) | 224 | = the baseline on the same model; the gain is the model's |
| final, held-out / all 41 | gpt-5.4, 3 runs, pooled | 0.388 / 0.877; 0.394 / 0.856 | 427; 651 | the headline; precision -0.316 [-0.392, -0.232] against LAsset RTL-only on all 41, recall +0.102 [+0.037, +0.167] |
| levers on gpt-5.4 | the frozen MV+NONE+BF, held-out (3 Oct) | 0.405 / 0.847 (vote) | 395 | not adopted: +0.011 [-0.004, +0.029] over MV, recall -0.037 |
| LAsset RTL-only (published) | | 0.680 / 0.748 (tuning); 0.730 / 0.757 (held-out) | 122; 196 | like-for-like row |
| LAsset spec+RTL (published) | | 0.737 / 0.910; 0.734 / 0.862 | 137; 222 | |

Tuning rows unless marked. Paired deltas against the baseline: `ismr` dP +0.015 [-0.011, +0.043], dR -0.028 [-0.104,
+0.046] (the pooled recall loss, -0.069, sits in `cpu`); `ismc` against `ismr` dP -0.002 [-0.025, +0.028], dR -0.001
[-0.042, +0.040]; `ismd` dR +0.031 [+0.005, +0.058]; `ist` dR -0.138 [-0.243, -0.031]; `ist2` against `ist` dR +0.068
[+0.015, +0.127]; gpt-5.4 against gpt-5-mini on the `ist2` prompt dP +0.086 [+0.035, +0.143]; final against `ist2` on
gpt-5.4 dP +0.006 [-0.025, +0.040], dR +0.010 [-0.040, +0.076].

## Arms

### Step 2, 21 Sep: six frozen rules over the map, by code (no model call)
Before scoring (`step2/RULES.md`): carrier copy, carrier field, port forwarding, clock and reset inputs, transport
records, a whole record beside its own fields; each with a stated basis (SAIF, LAsset p2, P3164). Bar: precision +0.10
with recall no worse than -0.03 on the baseline's stored runs. The file says R2 was chosen after looking at the tuning
modules. Got: 0.344 / 0.847 to 0.433 / 0.802; R1 and R2 do all the work (0.367 / 0.820 after R1, 0.431 / 0.802 after
R2), R3 to R6 move nothing. +0.089, -0.045: not substantial. With a majority vote 0.455 / 0.829 (reported, not part of
the bar). Not in any log at the time; re-derived here. Next: the map as the model's input.

### `ismr`, 30 Sep: the map section, LLM-written map
Before the run (NB-meta cell 18): counts only at P >= 0.374 and R >= 0.83; below that the map adds nothing to
generation. The map is never a candidate list (v2p3c1 "became a menu"). Got: 0.353 / 0.778, 244.7 listed. Fail. Recall
trace (`hand_arms/m7e194es0ismr/recall_trace.md`): 12 entries lost, 3 gained; 4 lost are `cpu` signals wired only
through sub-block port maps, which the map marks "not assigned" and the model never reached. Design flaw found by an
agent review on 30 Sep: the map's line numbers were original-file lines beside un-numbered RTL, so 0 of 5,760 line
references pointed at anything the model could see. Next: `ismc`.

### `ismc`, 30 Sep to 1 Oct: the same section, code-written map
Before the run: same bar; read against `ismr`, a difference being the map's accuracy (code 0.988 against E3's about
0.98 / 0.90 on the gold). Got: 0.346 / 0.787, 252.3 listed. Fail; `ismc` minus `ismr` dP -0.002, dR -0.001. Map accuracy
is not the lever: in `cpu`, where the recall is lost, the two maps are identical (22 records, REL). The section's cost
is real when pooled (recall -0.098, permutation p 0.048) and nearly absent on the six peripherals (REL). Next: a
counter-example check of every prompt idea in code before writing it (REL, 30 Sep); then `ismcap`.

### `ismcap`, 1 Oct: one bullet, a captured input is a setting point (RTL only)
Before the run (`hand_arms/read_cap_arm.py`): the winner lists 4 target inputs in 2 of 12 run-slots; falsified if the arm
reaches 4 or fewer; guards on clock/reset pins, transport ports, first-stage registers. Bound by re-scoring: +3.3 to +4
hits per run. Got: 0.355 / 0.829; targets 4 of 12: falsified. The hit movement is noise (permutation p 0.40, REL); the
bullet worked only where the capturing register is in the same entity (`sys enable_i` 1 to 3 of 3); RX paths are
anchored at the FIFO boundary, a sub-block. The FP drop (-36 slots) is mostly writing less. Next: code filters NONE and
BF, read on held-out.

### `ismq` / `ismrq`, 1 Oct: the four questions inside the generation call
Before the run (NB-meta cell 30, `read_q_arms.py`): counts only if neither P nor R falls more than 0.03 below the base
and the negatives are real; fail if excluded values name more than one reference entry per run. Risk named: v2sec's
second list cost recall 0.925 to 0.628. Got: `ismq` 0.352 / 0.754 (recall -0.093), `ismrq` 0.360 / 0.697 (-0.081):
fail, harmful. Compliance 100% / 98% of concepts answered; confidentiality "yes" on 0 of 331 and 0 of 353; integrity
"yes" on 327 of 331 and 351 of 353; excluded values 22 and 18 in total, naming a reference entry 3 and 5 (1.0 and 1.7
per run; `ismrq` fails that line). The one argument ("the RTL uses this value") survives any schema; the required
negative is trivial. Next: `ismd`.

### `ismd`, 1 Oct: the definition rules (deciders primary in their own right; transit registers secondary)
Before the run (`read_def_arm.py`): R1 false-positive slots on a frozen list of 17 transit registers (33 in the winner)
fall by at least half; R2 hits on deciding elements not lower; R3 five protected registers stay in 2 of 3 runs; R5
emissions within 10%. Got: 0.340 / 0.877, 286.3 listed; R1 33 to 43: fail; R3 5 of 5 at 3 of 3: pass; recall +0.031
[+0.005, +0.058] paired, precision 0.000. 0 of 378 concepts use the rule's wording; transit registers still labelled
"stores". Not adopted: the fourth prompt arm whose exclusion sentence changed nothing. Next: held-out reading.

### Held-out, 1 Oct: the baseline on the 26 unseen modules with the frozen code levers (read once)
Before the run (HPR): 18 files pinned; R1 adopt MV+NONE+BF if its precision gain over MV has a 95% module-bootstrap
interval above zero and its recall is at least 0.83; GUARD secondary only, against random thinning of equal strength
(it was derived from the tuning reference: on the held-out reference the condition gap shrinks from +0.52 to +0.175,
interval including zero, REL). What is not blind: two conventions (clock/reset inputs and bus-transaction ports are not
assets) were checked on all 41 modules early and are in the prompt, so only lever differences are a clean test. Got:
base 0.352 / 0.852 (runs 0.341 / 0.852, 0.350 / 0.868, 0.365 / 0.836); MV 0.350 / 0.857; MV+NONE+BF 0.399 / 0.884, dP over
MV +0.049 [+0.025, +0.080], dR +0.026 [-0.021, +0.075]: R1 pass, adopted (tuning reference +0.037 [+0.016, +0.058]).
NONE alone removes 46.3 per run, 95% false positives; BF adds 9.0, 74% hits; GUARD removes 118, 91.8% false positives,
0.446 / 0.801 against random thinning 0.393 [0.383, 0.404] / 0.707, 0 of 1,000 draws reach it: weaker out of sample but
not noise; stays a secondary row (0.497 / 0.836 with the other three). LAsset on the same modules: spec+RTL 0.734 /
0.862, RTL-only 0.730 / 0.757. Next: traceability (`ist`).

### `ist`, 1 Oct: the traced restructure
Before the run (`read_trace_arm.py`): R1 at least 80% of cited references verified and invalid plus uncited at most 5%;
R2 every "yes" cites a real line; R3 recall guard 0.80 (the map in the input, the four questions and a side list had
each cost recall before); adoption: the Step 1b bar and R1. Inputs: numbered RTL, map with occurrence IDs, code flow
graph. Got: 0.359 / 0.691, 213.7 listed; R1 687 of 846 verified = 0.812 with today's checker (0.944 on disk before a
later rule refused transport ports cited through a field; LED): pass; recall fail. 276 of 276 concepts cite map facts
(`ism` 0 of 349), but the answers are uniform: integrity yes 274 of 276, confidentiality no 276 of 276 (REL). 20
reference entries found by `ism` in 2 or more runs lost; 19 run-slots parked in the influence list; a post-pilot rule
that let a port named whole cite its field's record reopened the transport class (98 of 112 transport references, about
40 FP slots; my error). Counterfactuals on its outputs: transport filter + promoted influence + input back-fill + vote
0.403 / 0.802 (REL). Next: `ist2`.

### `ist2`, 2 Oct: generation without the questions, CIA in a separate call
Before the run (`read_ist2.py`): R1 at least 90% verified; R2 R >= 0.817 and P >= 0.344; R3 concepts per run >= 105;
R8 entries lost against `ism` <= 8; adoption: Step 1b bar. Design from the evidence workflow: `ismrq` (map + questions,
no influence list) had scored the same as `ist`, so the recall cost is the map in the input (about -0.07) plus the
questions in the call (about -0.09). The inherited confidentiality criterion ("require an RTL restriction on
disclosure") is not P3164's question; the labelling call asks P3164's. Integrity of values crossing the entity boundary
to an unsupplied consumer is assumed (P3164 Q2), after a Claude pilot listed 1 of 14 on `cpu` without it. Got: 0.343 /
0.733, 237.3 listed; verified 778 of 951 = 0.818: R1 fail; R2 fail; concepts per run 102.3: R3 fail; lost against `ism`
16: R8 fail. Against `ist`: recall +0.068 [+0.015, +0.127]. Next: the Claude-executor optimization loop on this prompt.

### Optimization loop, 2 Oct (OPT): Claude agents as executor, three edits
Before the loop: fixed set and scorer; every executor's file access audited; a change from observed error patterns,
worded generally, kept only when F1 beats the v0 mean by 0.03 (two v0 runs differ by 0.027); every edit needs a basis
row of ASSET_DEFINITION (tightened on 2 Oct after edit D failed review). Got: v0 (the `ist2` prompt) 0.335 / 0.887 over 2
runs; v1 (A: a stored register needs a use record; B: no one-clock copies; C: inputs into unsupplied sub-units "set")
0.371 / 0.934 over 3, F1 0.531 against 0.486: kept. v2 and v3: no edit beat noise; R1a (a register feeding only output
ports) went to the evaluation layer. Held-out, pre-registered, one run each (`HELDOUT_CHECK_PREREG.md`): v1 0.329 /
0.931 against v0 0.310 / 0.899, dP +0.019: "direction only, within noise"; R1a removed 23 FP and 8 hits and random
thinning reached its precision in 24.8% of draws: tuning fit, rejected. Every large false-positive family has hits of
the same record shape (state registers 53 against 19, settings 22 against 16): reference inconsistency, not a
structural rule. Next: the final version on a stronger OpenAI model.

### Final version on gpt-5.4, 2 Oct (`read_final.py`)
Before the run: F1 precision gain over the paired baseline (the `ist2` prompt on the same model) supported at +0.03;
F2 recall within -0.03; F3 edits A and B followed (half the removable entries); F4 the five `cpu` interrupt and debug
ports; F5 citations verified; a run counts only when complete. Got: final 0.407 / 0.820 (runs 0.418 / 0.784, 0.385 /
0.829, 0.418 / 0.847), 224.0 listed; the paired baseline lost a module in its third run (API credits exhausted, `wdt`),
so the readings fall back to `ist2` on gpt-5-mini (0.343 / 0.733, +0.064 "supported") and are labelled confounded. On
the same model, 2 complete runs: 0.407 / 0.815; paired dP +0.006 [-0.025, +0.040]. The gain over gpt-5-mini is the
model's; the edits add nothing measurable on gpt-5.4 (F3 "not followed": 17.3 removable per run against the baseline's
15.7; F4 5 / 5 / 5 against 3 / 3 / 1; F5 1.00 / 0.97 / 0.96 against 0.84 / 0.87 / 0.93). Held-out generation after the
credits were topped up (78 calls, at most USD 46 at list price, `logs/TIMELINE.md`): 0.388 / 0.877; all 41 pooled 0.394 /
0.856 against LAsset RTL-only 0.711 / 0.753 (dP -0.316 [-0.392, -0.232], dR +0.102 [+0.037, +0.167], module bootstrap).

### Levers on gpt-5.4, 3 Oct (not pre-registered for this model; `map_pipeline/levers41.py`)
Rule R1 applied after the fact. Got, held-out: MV 0.394 / 0.884 to MV+NONE+BF 0.405 / 0.847; dP +0.011 [-0.004, +0.029],
dR -0.037 [-0.063, -0.015]. The interval includes zero, so R1 would not pass; the headline stays lever-free. Why: gpt-5.4
quotes a code line for 18.0% of its held-out listings (gpt-5-mini 74.7%, TIMELINE), so NONE rests on the map's label
check, whose "stores" rule needs storage class "edge"; 51 of its 56 "stores" drops are clocked registers with a constant
tie-off ("mixed"), and 16 of the 56 are hits. The rule stays as frozen; a changed rule would be a new, untested lever.

## Where the study stopped

- **The answer to the question is no.** As generator input the map is a null on precision and costs recall in the
  restructured prompts; after generation it is worth +0.049 on gpt-5-mini (pre-registered, adopted) and +0.011 on
  gpt-5.4 (interval including zero). Final: gpt-5.4, all 41 modules, 0.394 / 0.856 against LAsset RTL-only 0.711 / 0.753.
- **Why the false positives stay** (final prompt, gpt-5.4, 1,953 listings over 3 runs on all 41 modules,
  `map_pipeline/fp_trace41/gpt54/ledger.csv`): 97.1% of false positives (1,149 of 1,183) and 99.5% of hits (766 of 770) cite an
  occurrence and a record the map holds; a listed "stores" element is a hit 245 times in 969 (25.3%), "computes" 86 in
  392 (21.9%), "sets" 211 in 291 (72.5%), "exit port" 228 in 301 (75.7%); 948 listings (48.5%) cite a clock edge, 243 of
  them hits. Rules learnt on the tuning modules raise held-out precision 0.388 to 0.545 but cut recall 0.877 to 0.598;
  a hit-versus-false-positive score from the map's relationship profiles reaches AUC 0.678 on the tuning modules and
  0.875 on held-out (`FINAL_NOTEBOOK.ipynb`). The reference lists the same kind of element in some modules and not in
  others (FSM state for the bus and the multiplier, never for the cache, TAP, SPI or TWI; REL).
- **On LAsset's own published list the map is an audit trail, not a filter** (pre-registered, read once, 2 Oct): a
  map-profile model trained on tuning ranks LAsset's held-out hits above its false positives at AUC 0.639, 97.5% interval
  0.495 to 0.768; the filter threshold fixed on tuning was zero, so nothing was dropped and H2 was not testable.
- **What stayed:** every listed asset of the final pipeline cites an occurrence ID and a record that code checks
  (1,915 of 1,953 pass); the two structures as module portraits; the held-out discipline.
- **Side readings, same period** (REL; `blind_agent/REPORT.md`): seven blind Claude analysts with RTL + map only,
  primary P 0.262 R 0.744 against the winner's 0.294 / 0.814 on their modules, 122 of 122 citations real; prompts
  written from theory alone cap at about P 0.36 / R 0.6 (D1: tuning 0.359 / 0.577, held-out 0.362 / 0.619), listing port
  record fields the reference never has and leaving out the strobes and enables it lists: the gap is reference
  convention, not reasoning.
- Hand-off: the fourth study (a two-phase prompt on a code-built block diagram, from 10 October, `experiments/03_two_phase_csa_pio/lab/`).

## Corrections kept in the log

- The relation-writer position reversed twice (REL, 29 to 30 Sep): code (adjudication) to open (E3 beat the current
  code on the gold) to code (the six-fix writer, frozen before scoring).
- "At most 30% of quoted assignments are verbatim" was a parser bug: 84.8% reproduce an RTL statement (REL, 30 Sep).
- `ismr` / `ismc` showed original-file line numbers beside un-numbered RTL: a design flaw of both arms, found after
  the runs.
- GUARD: "overfitted" (1 Oct, before the reading) softened to "weaker out of sample but not noise" after it.
- `ist`: the via-field citation route that reopened the transport class was my addition after the pilot.
- `ist` citations: 0.944 on disk, 0.812 with today's checker (a later rule refuses transport ports cited through a
  field); `ist2` 0.818 misses its own 0.90 bar either way.
- "FPs cannot be controlled" (2 Oct) replaced by the measurement: structural rules remove part of them at a recall
  cost; the rest share their map evidence with hits.
- "21 relationship classes" were 13 classes plus 8 element attributes; "FPs in concepts with no reference element"
  counted every asset under its first concept only (59% to 55% on tuning, 44% on all 41) (TIMELINE).
- The August reading that LAsset's precision comes from its refinement stage was wrong: 0.737 before refinement,
  0.800 after (3 Oct).
- A first draft of the final notebook read the higher all-41 AUC as "the differences do not weaken on unseen modules"
  and withdrew the earlier reading; a claim audit split it by module set and the withdrawal was reverted the same day.

## Re-derived against logged

All precision, recall and listed-count figures above reproduce REL, NB-meta, HPR, OPT and LED to the third decimal
(`map_pipeline/levers41.py` and `map_pipeline/results41.py` self-tests pass first: the 17 recorded tuning stacks, the stored
held-out reading and the gpt-5.4 base rows). Differences: the `ist` citation share (0.812 here, 0.944 on disk, see
above); the Claude held-out dP (+0.019 pooled, as registered; the module-paired mean is +0.041 [+0.003, +0.098], a
different statistic); the final gpt-5.4 tuning precision (0.406 pooled over modules, 0.407 as the mean of three per-run
values). Not re-derived here: the LLM-stage counts of the profiler and the relation annotator (REL, NB-meta), the
blind audits, the gold sample itself, and the citation share of the gpt-5-mini runs (TIMELINE).
