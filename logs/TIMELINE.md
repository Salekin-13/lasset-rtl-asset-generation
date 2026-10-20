# Timeline: July to October 2026

What was decided, why, what was measured, and what was learned, month by month. Negative results and
corrections are kept on purpose. Decisions marked **KEY DECISION** are the ones that best show how the work
was judged, not only what was built.

## How to read this

- **Precision (P):** of the elements a method lists, the share that are in the reference.
  **Recall (R):** of the reference entries, the share the method lists. Both are named every time.
- **Reference:** the LAsset authors' manual "True Assets" list for NEORV32 (`data/ground_truth/manual_gt_neorv32.json`).
  **Tuning set:** 15 modules, 111 entries (`data/RTL_data/`). **Held-out set:** 26 modules, 189 entries (`data/RTL_heldout/`),
  not looked at while tuning.
- **Arm:** one variant (a prompt, an input or a filter) run against a fixed baseline, usually 3 runs.
  **Pre-registered:** the expected result and the decision rule were written down before the run.
- **Closed set:** the list of ports and signals extracted from the RTL by regex; an asset must name one of them.
- Every number is copied from the source named in brackets. Numbers marked *(re-derived)* are not in any log;
  they were recomputed in this session from stored runs, with no API call. Numbers marked *(derived)* are simple
  arithmetic on logged numbers.
- The scorer and the executor model changed over time. The scorer changed in early August (field-to-field matching
  removed on 08-02, metric M-2 on 08-03) and in smaller ways later (LED lists the differences). The executor was
  gpt-5-mini, then Claude agents and gpt-5.4 in October. Numbers inside one study are comparable. Numbers across
  months are approximate.
- Git: 9dc383d (2026-08-18) is the last commit of the August study. The September and October work was first
  committed on 2026-10-02, in the commit that prepared this repository (0851cca), followed by the layout move
  (`docs/LAYOUT.md`). So September and October dates come from dated log entries and file modification times.

**Source keys.** AL1 `logs/ABLATION_LOG.md` · AL2 `logs/ABLATION_LOG_V2.md` · HO `logs/V02_HANDOFF.md` · REG `logs/V02_REGISTRATION_DRAFT.md`
· VER `bahavioral_patterns_of_assets/VERIFIER_ABLATION_LOG.md` · PAR `bahavioral_patterns_of_assets/PARSER_ABLATION_LOG.md`
· REL `step1/lasset_step1/RELATION_EXPERIMENTS_LOG.md` · OPT `assetgen_meta/prompt_opt/OPTIMIZATION_LOG.md`
· DEF `assetgen_meta/ASSET_DEFINITION.md` · HPR `assetgen_meta/HELDOUT_PREREG.md`
· HCP `assetgen_meta/prompt_opt/HELDOUT_CHECK_PREREG.md` · LLP `assetgen_meta/lasset_layer/PREREG.md`
· LLR `assetgen_meta/contribution_assessment/5_lasset_layer_result.md` · LED `.../contribution_assessment/1_evidence_ledger.md`
· SKP `.../contribution_assessment/4_skeptical_review.md` · TG `docs/TUNING_GUIDE.md`
· ESA `assetgen_meta/error_analysis_screen1.md` · RCL `.../occurrence_prompts_v3d/RULEBOOK_CHANGELOG.md`
· S2 `step2/RULES.md` · NB-meta `notebooks/assetgen_meta.ipynb` · NB-step1 `notebooks/lasset_step1.ipynb`
· NB-final `FINAL_NOTEBOOK.ipynb` · GIT `<commit>`.

---

## Headline numbers over time (tuning set unless marked)

Different executors and scorer versions; read as a trajectory, not as like-for-like deltas.

| Date | Version | Set | P | R | Source |
|---|---|---|---|---|---|
| 2026-08-03 | v0, first ablation baseline | tuning | 0.300 | 0.553 | AL1 §4 |
| 2026-08-07 | v01c6, end of the recall study | tuning | 0.229 | 0.881 | AL1 §4 |
| 2026-08-08 | v01c6p1p2, RTL-only input | tuning | 0.243 | 0.886 | AL1 P-2 |
| 2026-08-08 | v2, precision-study baseline | tuning | 0.251 | 0.925 | AL2 §5 |
| 2026-08-10 | v2x3r8, best v2 precision (failed the recall guard) | tuning | 0.296 | 0.853 | AL2 X-3R-8 |
| 2026-09-19 | m7e194es0c, meta-prompt seed, 3 runs | tuning | 0.379 | 0.787 | NB-meta cell 10 output |
| 2026-09-20 | m7e194es0ism, Step 1b winner | tuning | 0.344 | 0.847 | AL2 §10 |
| 2026-10-01 | winner + MV+NONE+BF code filters | tuning | 0.394 | 0.901 | REL, HPR |
| 2026-10-01 | winner + MV+NONE+BF, pre-registered, read once | **held-out** | 0.399 | 0.884 | REL, AL2 §10 |
| 2026-10-01 | ist, traced arm (cites occurrence IDs) | tuning | 0.359 | 0.691 | REL |
| 2026-10-02 | loop v1, Claude executor, mean of 3 runs | tuning | 0.371 | 0.934 | OPT |
| 2026-10-02 | loop v1, Claude executor, 1 run | **held-out** | 0.329 | 0.931 | OPT |
| 2026-10-02 | loop v1 on gpt-5.4, 3 runs | tuning | 0.407 | 0.820 | OPT |
| 2026-10-02 | final prompt on gpt-5.4, 3 runs (pooled) | **held-out** | 0.388 | 0.877 | NB-final |
| 2026-10-02 | final prompt on gpt-5.4, 3 runs (pooled) | all 41 | 0.394 | 0.856 | NB-final |
| reference | LAsset initial, spec + RTL | tuning / held-out | 0.737 / 0.734 | 0.910 / 0.862 | DEF §4 |
| reference | LAsset initial, RTL only (like-for-like row) | tuning / held-out | 0.680 / 0.730 | 0.748 / 0.757 | DEF §6 |

---

## July 2026

### Replication of LAsset (Algorithm 1, lines 3-5)

- **Chose an 18-file NEORV32 subset to tune on.** Why: to save tokens while tuning
  (`notebooks/finetuning_assetgen.ipynb` markdown cell 2). 15 of the 18 have reference entries. `boot_rom`, `fifo` and
  `package`, which the paper pruned, were kept as the only negative controls: "a prompt that cannot say 'no assets
  here' will invent them" (AL1 C-01). RTL files are dated 2026-07-12; first commit 694384a on 2026-07-20.
- **Built the paper's stages as written where the paper is specific, and declared our own choices where it is not.**
  SpecRAG (retrieval of datasheet passages into a summary) at the paper's parameters: chunk 1000, overlap 200,
  top-k 20, ada-002 embeddings (AL1 C-02). Datasheet text added 2026-07-20 (GIT ca50c49); retrieval cache dated
  07-21, summaries dated 07-23 (file dates). An early report mapping LAsset's listed assets to RTL files and entities
  is dated 2026-07-16 (`asset_traceability_report.json`, not published).
- **The closed set is extracted by code, not by the LLM.** Why: "An asset that does not name a real element is
  unverifiable, so the closed set has to be ground truth rather than a model output" (AL1 C-03). The LLM only
  annotates what each element means. Settled before the study opened on 2026-08-02.
- **First full generation run and a root-cause pass over its false positives.** 163 false positives (FPs) were
  assigned to a pipeline stage: core prompt 72 (44%), post-filter 46 (28%), in-context (ICL) examples 29 (18%),
  parser 16 (10%) (TG §2). *Date not in the repo; TG (committed 2026-08-03) calls it "an earlier pass", and a session
  note dates it 2026-07-25/26.*
- **Two early prompt ideas failed and became standing rules** (recorded in AL1 without a date, so before
  2026-08-03):
  - A numeric cap ("stop at ~20% of the closed set") "cost 7 of 17 recall losses on `cpu_cp_cfu`, whose
    ground-truth density is 38%" (AL1 A-03). Learned: a number in a prompt becomes a hard quota, however it is
    hedged. This later became a code-enforced rule (no numeric hints in prompts).
  - A free-standing checklist of signal types "became a generator once before (`cpu` emitted `ctrl.*` eleven times)"
    (AL1 A-02).
- **Rejected our own first ICL examples.** The v1 examples were "fabricated rather than sourced": names such as
  `dir_sel_i`, `pad_io`, `lfsr_state` "appear nowhere in P3164" (AL1 A-01). Dropped from the study (GIT ab9d295,
  2026-08-03). The replacement examples use real published IPs with published labels.

### RTL parsing

- **2026-07-31, architecture-scope parser bug fixed** (GIT 4e14528). The regex stopped at the first inner `begin`,
  so `neorv32_cpu_cp_crypto` parsed to zero internal signals; after the fix it yields 27, and the 18 cached closed
  sets are byte-identical. Two latent bugs fixed at the same time (initialised signals, port defaults).
- **Reference extracted from the LAsset release** (GIT 4e14528): manual list 41 modules, 246 rows, 301 elements
  against the paper's stated 302; LAsset initial list 359 assets; refined list 331.
- **Evaluation framework.** TP/FP/FN with P, R, F1 and deliberately no false-positive rate, because negatives
  outnumber positives about 14:1, so FPR read 0.107 while precision was 0.324 (GIT 4e14528). A truncated model
  reply had been cached as a genuine "no assets" answer; fixed.

---

## August 2026

### Replication of LAsset: the recall study (v1), 2026-08-02 to 08-08

- **2026-08-02, a scorer bug that flattered our own results was found and fixed** (GIT 7289331). Field-to-field
  matches were credited (a predicted `fifo.avail` scored against a reference `fifo.re`). Recall dropped
  v0 0.573 → 0.536 and v1 0.709 → 0.691. The ablation layer was added: repeats, and a paired bootstrap with modules
  as the pairing unit.
- **2026-08-03, ceiling analysis before tuning.** If parsing were perfect, recall could rise at most to 0.991, so
  about 0.30 of recall loss sits in the generation stage, a 33x difference (GIT 74fd849; TG §1). Re-audited
  2026-08-07: two reference entries cannot exist in our RTL version (`inval_i` is `inv_i` here; `cache_o.cmd_dir`
  has no such field), so the ceiling is 0.982 (AL1 C-03).
- **2026-08-03, `logs/ABLATION_LOG.md` opened.** Every arm gets an `Expect:` and a decision rule before it runs, and the
  `Got:` is pasted from code, never retyped (AL1 header; R-03 records a retyping error that motivated this).
- **2026-08-03, metric M-2.** Two same-name elements in different entities had been collapsed into one; this was
  the whole reason the reference totalled 301 instead of 302. Fixed by re-scoring, not re-running: A-00 recall
  0.552 → 0.553 (AL1 §5 M-2).
- **A-00, noise floor** (v0, 3 runs): recall sd 0.019, F1 sd 0.010; P 0.300, R 0.553 (AL1 A-00, §4). Learned:
  modules, not repeats, limit what can be detected; the paired recall interval is about ±0.14 wide with 15 modules.
- **A-01, ICL examples** (v01). Port recall +0.181 [+0.048, +0.302], signal recall −0.157 [−0.229, −0.086],
  aggregate recall +0.049 (null) (AL1 A-01). Decision: **per-class recall becomes the primary metric**, because the
  aggregate hid two real effects that cancelled (GIT 3041ade). Also learned: the spec summary was not the bottleneck
  (modules whose summaries named none of their port assets still went 0.355 → 0.645). A-01x: no example can fix the
  signal loss, because every labelled example IP is 75-100% ports while NEORV32's reference is 42% port / 29% signal
  / 28% signal-field (AL1 A-01x).
- **A-02, "role, not location"** (v01c2, 2026-08-03 to 08-04). Port recall +0.262, signal recall +0.106, aggregate
  recall +0.162 [+0.083, +0.232], precision −0.001 (AL1 A-02). The pre-registered rule fired and v01c2 became the
  baseline.
  - **KEY DECISION (pre-registration kept honest).** On 2026-08-05 the stated *basis* of one prediction was found to
    be a misreading. The correction was added beside the registered text, not edited into it: "a pre-registered
    block quietly corrected after the result is known is no longer pre-registered" (AL1 A-02).
- **A-03, port-record granularity** (v01c3, 2026-08-05 to 08-06). An oracle predicted P 0.338; the arm reached
  0.315, with port-field FPs 72.7 → 1.7 per repeat. A control arm on the other core (n=2, directional only) showed
  the same sign (AL1 A-03). Learned: the rule was a rename, not a removal (port-field FPs 73 → 2, whole-port FPs
  19 → 55).
- **T-1, diagnostic: are misses "never conceived" or "conceived but not bound to the element"?**
  (2026-08-06 to 08-07). First write-up blamed the prompt: 0 of 90 files had the concept list. **Correction:** our own
  code had dropped the field (`generate_assets` rebuilt the reply from two keys); 90 calls were lost. Three guards were
  added. Re-run (v01c5): 82.1% of misses were binding failures, quoted as about 82-85% after the judge's own
  run-to-run variance was measured; every strong "never conceived" case was Availability (AL1 T-1 and addendum).
- **A-08, per-concept closure sweep** (v01c6, 2026-08-07). The first arm to raise the union-over-repeats ceiling
  (recall of everything found in any run): 0.928 → 0.955. Recall +0.027 [+0.009, +0.046], precision −0.038
  [−0.057, −0.021] (AL1 A-08). Promoted by its rule. Learned: precision 0.229 against the paper's 0.737 was now
  "the binding problem" (AL1 §6).
- **Near-match audit** (2026-08-07): lenient matches were 0.4% of true positives at v01c6, and every version-to-version
  gain survived exact-only matching. The metric was kept, and the near-match count was printed for every arm
  (AL1 §5).
- **P-1, drop the spec summary** (v01c6p1): null on recall, precision and F1 (HO; AL2 §3). *AL1's own `Got:` line for
  P-1 is empty; the result is recorded in HO and AL2.*
- **P-2, drop the parsed closed set and let the model read declarations from the RTL** (v01c6p1p2, 2026-08-08).
  - **KEY DECISION (re-checking a confident rejection).** P-2 had first been dropped as impossible, for three
    "careful-sounding" reasons. All three rested on one false premise: that the closed set *is* the JSON blocks
    rather than an abstraction the RTL already contains. Reinstated 2026-08-08 with the lesson "re-check the premise
    that makes it impossible" (AL1 P-2).
  - Result: recall −0.020 [−0.086, +0.039] (null), precision +0.017, emissions 476 → 404, and 58.0% of every user
    message removed. Three of four predictions were wrong. The model produced 187 names outside the parsed set and
    invented none: all were real RTL identifiers our regex had missed. Costs: union ceiling 0.950 → 0.937, recall
    variance about doubled (AL1 P-2). Promoted.
- **L-1, leak audit** (2026-08-08).
  - **KEY DECISION (no answers in prompts).** A naming example in the prompt, `ctrl_i`, is a reference answer in
    10 of the 41 annotated modules, 9 of them in the future held-out set. Worth at most 0.009 recall on tuning, but
    "disqualifying for the measurement that matters most". Fixed as a new version rather than an in-place edit, so
    no recorded run's sha changes. Standing rule: no identifier from the 41 modules may enter a prompt
    (AL1 L-1; HO). Later enforced at import by code (`audit_against_corpus`, `prompts_v2.audit`).
- **What the paper comparator contains** (2026-08-08). LAsset's initial list carries primary and secondary assets;
  our comparator uses primaries only (137 emissions, P 0.737, R 0.910). About half our FPs are elements LAsset names
  as *secondary* (v01c6: 175 of 331, 52.9%) (AL1 §5 M-2 addendum). Deferred by decision.
- **Stated plainly at the close of v1:** "We are not outperforming the paper. We reach comparable recall by naming
  three times as much" (404 against 137); and five arms were designed after inspecting misses on the same 15
  modules, "fitting to the test set" (HO). This is the reason a held-out set was later obtained.

### Prompt studies: the precision study (v2), 2026-08-08 to 08-18

- **2026-08-08, objective switched to precision, with recall as a guard** (GIT 699a3a5; AL2 §1-2).
  - **KEY DECISION (the recall guard is a decision rule, not a code path).** Regenerating when recall falls would
    select on the answers, so the guard is applied only at the results table: an arm whose recall drops more than
    0.03 below its baseline does not become the baseline; 0.03-0.06 means re-run at n=5. It is judged on the point
    estimate, because a ±0.14 interval would never fire (AL2 §2).
  - The registration draft called F1 "the wrong decision metric". **Correction:** tested on real arms, F1 stays flat
    when an arm only emits less and rises when it removes false positives cleanly, so F1 became the second headline
    metric (REG header; AL2 §8 R-V2-01(b)).
- **Measured headroom before running anything** (AL2 §6). Deleting every concept that produced no true positive, an
  oracle, tops out at P 0.362. So 57% of FPs (173.4 of 305.7 per run, AL2 §6 table) sit inside concepts that also
  produced a true positive; the log's own sentence says "about two-thirds", which its table does not support.
  Learned at the time: generation-stage prompting alone cannot reach 0.737; the paper gets there with its refinement
  stage. **Corrected 2026-10-03:** that inference was wrong. LAsset's spec+RTL list scores P 0.737 *before*
  refinement and 0.800 after on the tuning modules (held-out 0.734 -> 0.791), so its precision comes mostly from its
  generation step (`assetgen_meta/ASSET_DEFINITION.md`:15, 78-82).
- **v2 baseline** (RTL only, plus three corrections D, L, N): P 0.251, R 0.925; paired precision +0.024
  [+0.007, +0.042] (AL2 §5). The registered prediction was "about the same as before", so it was recorded as wrong.
  Correction D (the prompt no longer refers to inputs that are not sent) cut ungrounded names 187 → 106. Correction N
  admitted that L-1's test ("is this name an answer?") was the wrong test: `clk_i` / `rstn_i` stated a correct
  negative fact about 46 real elements (AL2 §3).
- **Rejected before running:** a blind per-concept cap; at cap 4 it buys +0.022 precision for −0.201 recall
  (AL2 §8 R-V2-01(a)).
- **S-1, container vs content** (2026-08-09 to 08-10): precision −0.009 [−0.023, +0.006], null, rejected. The
  exception for "entropy" fired everywhere in the TRNG (emissions 14.0 → 20.0 per repeat). Rule recorded: a null is
  not re-worded and re-run (AL2 S-1).
- **R-8, revert the A-08 sweep** (2026-08-10): mechanism confirmed (largest concept 53 → 12 elements), precision null
  (+0.005 [−0.011, +0.019]); the registered cost, losing the union ceiling, did not happen (AL2 R-8).
- **X-3 and X-3R-8, a third ICL example and the combination** (2026-08-10). Both were **run without
  pre-registration**, which the log states and handles by judging them only against the standing guard (AL2 X-3).
  X-3R-8 gave the first distinguishable precision gain, +0.025 [+0.013, +0.038], but recall fell 0.925 → 0.853, so
  the guard failed and the arm was rejected. It cut the best-precision class (ports, −31.4% emissions) hardest and
  the worst one (signal fields, −16.9%) least. A causal claim made in the first analysis was withdrawn when a control
  run showed the same pattern (AL2 X-3, X-3R-8).
- **S-3, "routed traffic belongs to the fabric"** (2026-08-11): precision −0.016 [−0.036, −0.001], rejected. The
  prohibition worked where it applied (fabric-typed FPs 76.0 → 55.7 per repeat), but its redirect ("name the
  decision elements instead") became a licence elsewhere (TRNG emissions +76%). Rule recorded: prohibit without
  redirecting (AL2 S-3).
- **SEC, give the model a "secondary" list** (2026-08-11): precision +0.069 [+0.006, +0.131], the largest gain of
  the study, but recall 0.925 → 0.628, rejected. The registered mechanism check passed: 117 of 123 elements that left
  the primary list reappeared as secondary (95%). A conflict registered beforehand also materialised: SAIF calls FSM
  state secondary, the reference lists it as primary, and 5 of 7 such elements were lost (AL2 SEC).
- **RP, P3, C1: restore the parsed list with annotations** (2026-08-16 to 08-18). RP (152-label role taxonomy):
  P 0.210, R 0.855. The taxonomy was dropped for P3 because eight role names restated the asset rubric, so "the
  parser fills in STEP 1's answer sheet". C1 (open-vocabulary parse plus a reading procedure): P 0.249, R 0.848,
  against v2's 0.250 / 0.930 in the same table (AL2 C1). Learned: the recall loss is instability, not blindness
  (elements found in all three runs: 0.727 against v2's 0.882, with the same union). *LED re-derives C1 as
  P 0.240 / R 0.847 with today's scorer; the log predates later scorer changes.*
- **Correction to the A-03 story** (AL2 C1): of 49 bare-port reference assets exactly one is a record port; record
  interconnect ports are not assets at any granularity.
- Committed 2026-08-18 (GIT 9dc383d). This is the last commit of the August study.

### RTL parsing and the parser/verifier work, 2026-08-17 to 08-22

- **Parser generations 1-3** (2026-08-17; AL2 C1). Writing edge names bare fixed 233 malformed types; constraining
  targets to declared names cut unresolved targets 589 → 8. A sweep for governing sites moved coverage only
  218 → 215: read as a model limit, so no third revision. A gen3 rule backfired (prose claiming governance 245 → 288
  while governing edges fell 215 → 201) and was reverted. `src/parse_audit.py` was written to be blind to the reference
  "by design".
- **2026-08-18, element dossier and a blind triage** (`back_test.md`, `ASSET_ELEMENT_DOSSIER.md`; neither is published). A label-stripped
  copy was triaged for C/I/A/U by local agents (Section A 110 headings; Section B 1,095 of 1,531 entries;
  `bahavioral_patterns_of_assets/reference/PROCESS.md` and README, not published). An API prompt-ablation notebook (P0-P8) was built
  the same day. *Its results folders are empty: it was not run, and no outcome is claimed.*
- **Verifier study: make the instrument trustworthy before acting on its counts** (2026-08-21 to 08-22; VER).
  - **KEY DECISION (measure the instrument first).** A pure replicate agreed with the earlier run on 85.1% of claims
    (149/175). An earlier "effort ablation" had agreed 86.3%, so it was noise and its conclusion was withdrawn.
    SUPPORTED verdicts reproduced 98.1% of the time, PARTIALLY_SUPPORTED only 67.2% (VER V-1).
  - A deterministic coverage check: 0 elements omitted and 0 invented across 26 entities and 1,689 elements; two
    extraction bugs in the checker itself were found before the number was trusted (VER O-1).
  - Full pass (run_011, $30.23): 10,947 claims, 78.3% SUPPORTED, 1.8% CONTRADICTED. The dominant parser error: an
    asynchronous reset labelled `SEQUENCES`, 111 contradicted claims, 31.8% of all `SEQUENCES` claims (VER §7c).
    This fed the next parser revision (`parser_v4.ipynb` markdown cell 0: `RESETS` split out, guards required).

---

## September 2026

### RTL parsing: edge definitions, 2026-09-01 to 09-06 (PAR)

- **2026-09-01, 14 edge definitions rewritten and validated by four independent readers** on 22 real RTL sites:
  agreement 77% → 100% → 22/22 on type over three rounds (PAR §4.1).
- **2026-09-05, v5 parse.** Control couplings recorded at both ends 2% → 43%; output-port coverage 54% → 90%;
  governing coverage 51% → 56% ("mostly failed"). The prediction that `REFLECTS` would grow to about 44 came back 0,
  recorded as wrong (PAR §4.13). Learned: the model finds the sites and mislabels them, and "a rule stated in the
  prompt and never checked in code stays violated" (PAR §3B.4).
- **v6 (schematic shapes on all 14 edges): a net regression**, 3 of 5 pre-stated falsifiers failed (PAR §3C).
  v7 narrowed the shapes to three edges. Batch ordering by first use in the source raised same-batch pairs
  31% → 50%, as predicted; the author's own first guess (order by field name) was the worst option at 25% (PAR §4.25).
  *v7 was not run: there is no `parsed_v7_tuning18/` folder.*

### Occurrence profiles, 2026-09-09 to 09-29

An occurrence profile lists every place an element appears in the RTL, with its enclosing structure and a "SITE" tag
(what the occurrence does there: assignment target, condition, port map, and so on).

- **2026-09-09 to 09-14, hand annotation first.** The author profiled `neorv32_boot_rom` by hand
  (`annotation_process.md`, 2026-09-11) and drafted the SITE tags (drafts v1 09-12, v2 09-14). VHDL legality rules in
  the rulebook were tested with the ModelSim compiler (`vcom`) and the rulebook is edited in place, never regenerated
  (RCL, decided 2026-09-14).
- **2026-09-14 to 09-18, four-step LLM profiler (v2):** knowledge (LLM) → extract (code) → classify (LLM) → validate
  (LLM), checked against the hand key. Run 5 hand review: span errors 104 and structure errors 59 of 662 entries;
  run 6: 476 of 661 structure chains correct, every error at the branch level (NB-meta markdown cells 70, 78).
- **KEY DECISION (code where there is one right answer).** Structure is a parsing problem with one answer, so it was
  moved to code. 2026-09-21: code profiles for all 41 reference modules; SITE tags agree with a low-effort LLM on
  853 of 989 (86%), and where they disagree a rulebook adjudication found code right 53% of the time against the
  model's 38%; a 20-relation hand check scored 19/20 (NB-meta markdown cell 76).
- **2026-09-28 to 09-29, v3 and v3b.** A VHDL grammar (tree-sitter) supplies Context and Path to every occurrence.
  Structure chains wrong after validation: 22 (run 6) → 0. v3b caps batches at 85 occurrences after v3 lost 11 of one
  element's 34 rows in a 168-occurrence batch; cache back to 427 of 427 rows correct. Over all 44 files: 0 parse
  errors, 17,968 of 17,969 rows chained (NB-meta markdown cell 82). Recorded as a named deviation from LAsset
  §III-A.3, which describes LLM-based parsing.
- **2026-09-29, v3c and v3d on the 15 modules.** The v3b check report found two tag-rule gaps; three rounds of rule
  edits judged by code checks cut flagged entries from 26 (v3b) to 3 (v3d) on 2,142 test entries. The same prompt run
  twice changes 44 of 2,117 entries (2.1%), recorded as the noise floor (RCL; NB-step1 markdown cell 0).

### The relation map, 2026-09-21 and 09-29 to 09-30

The relation map records typed relationships between elements (one drives, gates, selects or carries another), each
tied to the occurrence where it happens.

- **2026-09-21, first code-built map and a zero-API rule test ("Step 2").** Six rules were frozen before scoring,
  each with a stated basis, and the file says openly that one rule (R2) was chosen after looking at the tuning
  modules (S2). Bar: precision +0.10 with recall no worse than −0.03. *Result not found in any log; re-derived this
  session with `step2/apply_rules.py`:* on the Step 1b winner, P 0.344 → 0.433 and R 0.847 → 0.802, "not
  substantial".
- **2026-09-29, LLM relation annotator, experiments E0-E4** (REL). An identical re-run (E1) moved the headline by
  2.0 points; linked batches (E2) lost 8.1 points; a repair pass (E4) lost 13.8 points and was rejected; a pair-first
  prompt (E3) gained 4.3 points. The headline metric was changed mid-study, with the reason logged: the old rate
  rewarded writing little.
- **Code or LLM as the relationship writer?** (2026-09-29 to 09-30; REL).
  - Blind adjudication of disagreements favoured code (right about 66.5% against the LLM's 28.3%).
  - On an independent gold set (120 occurrences kept out of the adjudication sample, on tuning modules; written blind
    by gpt-6-astra), E3 beat the *current* code on precision, so the position was reversed and logged: "the writer
    question is open".
  - A six-fix code writer was frozen (sha `b0e767000ec2`) before scoring on that gold set: typed P 0.988, R 0.988.
    Decision 2026-09-30: code writes relationships; the LLM keeps the prose descriptions.

### Prompt studies: Step 1b, meta prompts and hand arms, 2026-09-19 to 09-30

- **2026-09-19, Step 1b: rebuild the asset prompt as a top-down procedure.** A meta model (gpt-6-astra) writes a
  method and an execution prompt; the executor is gpt-5-mini on comment-stripped RTL. Rule: keep a prompt only if it
  adds at least 0.03 precision with recall ≥ 0.83. Baseline v2x3r8 (P 0.296, R 0.853) (NB-meta markdown cells 0, 7,
  14; cell 8). *v2x3r8 had failed the August recall guard (0.925 → 0.853); it served here because Step 1b set its own
  recall floor of 0.83.*
- **Six meta-prompt versions screened in one day (meta prompts v1 to v5s), none passed** (NB-meta cell 10 output;
  ESA; run folders `assetgen_meta/runs/meta_*`, all dated 2026-09-19):
  - Screen 1 (three samples): P 0.243 / 0.263 / 0.273, R 0.667 / 0.577 / 0.405. Cause: input-port recall 5, 4 and 1
    of 26 against the baseline's 21, 22 and 19; transaction records were the largest FP source, with 0 true positives
    in all runs (ESA §A).
  - Screen 2 seed (`m7e194es0`): P 0.380, R 0.829 on one run, one element below the floor *(derived: 0.829 x 111 =
    92 hits; 0.83 needs 93)*. Three fresh confirmation runs gave P 0.379, R 0.787: does not count.
  - With the annotator-convention filter applied to both, the seed's precision lead over the baseline shrank from
    0.083 to 0.039 *(derived from the cell-10 table: 0.380 vs 0.341)*. Learned: half of the apparent gain was
    reference conventions, not method.
  - Later screens (meta v3, two seeded arms, meta v5s) did not pass either: none reached recall 0.83; the best
    3-run result was P 0.339, R 0.808 (`m43f965s0`).
- **2026-09-20, hand arms on the seed:**
  - seed + two port-heavy ICL examples (`i01b`): P 0.374, R 0.742, does not count *(re-derived)*;
  - seed + two worked examples that apply the seed's own procedure (`ism`): **P 0.344, R 0.847, counts, the
    "winner"** (AL2 §10; NB-meta cell 21 output);
  - plus worked removals (`ismp`): P 0.336, R 0.844, below the winner *(re-derived)*.
  - Learned: examples buy recall; three rounds found no prompt-side fix for precision.
- **2026-09-21, held-out RTL obtained.** 26 reference modules with no tuning use, in `data/RTL_heldout/` (file dates
  2026-09-21), with closed sets built by `step2/build_heldout_parse.py`. This closes AL2's open threat "No held-out
  set exists" (AL2 §9, §10).
- **2026-09-30, relation map in the prompt** (NB-meta cells 21, 25): LLM-written map (`ismr`) P 0.353, R 0.778;
  code-written map (`ismc`, finished 10-01) P 0.346, R 0.787. Counter-example checks (REL): map accuracy is not the
  lever; a one-hop walk from reliable assets reaches 218 elements of which 4 are reference entries (2%).
- **2026-09-30, an independent agent review reversed two of the author's checks** (REL):
  - a parser for quoted RTL was wrong ("G REFUTED (my parser was wrong)"): 84.8% of quoted assignments reproduce a
    statement verbatim;
  - an arm design flaw: `ismr`/`ismc` showed map line numbers from the original file next to un-numbered RTL, so
    0 of 5,760 line references pointed at anything the model could see.
- **2026-09-30, trace built after generation, in code** (REL). Quote → occurrence ID → relationship record → label
  check. Full path for 186 of 282 true positives (66.0%) and 193 of 538 FPs (35.9%). A pre-registered blind audit
  passed 30/30, but the false positives also checked out: "a full path shows evidence exists, not that the reference
  agrees".
- **Reference version skew handled without editing the reference** (REL): `neorv32_cache` was annotated on an older
  NEORV32; a corrected overlay (110 entries) changes recall by +0.010 to +0.017 and no ranking.

---

## October 2026

### Prompt studies: hand arms and the asset definition, 2026-10-01 (REL)

- **Captured-input bullet** (`ismcap`): pre-registered falsifier "target inputs reach 4 or fewer of 12"; got 4 of 12,
  **falsified**. P 0.355, R 0.829. A permutation test put the reference-hit movement within noise.
- **Blind "engineer" prompt** (seven Claude analysts, one module each, RTL + map only): primary P 0.262, R 0.744
  against the winner's 0.294 / 0.814 on the same modules; 122 of 122 citations resolve to real occurrences.
- **Four P3164 questions inside the generation call** (`ismq`, `ismrq`): recall −0.093 and −0.081, precision within
  noise. The answers did not discriminate (integrity "yes" on 327 of 331 concepts, confidentiality "yes" on 0).
  Rejected as harmful.
- **What "asset" means, measured.** Scoring primary + secondary together was rejected (it rewards listing more:
  0.287 / 0.628 → 0.220 / 0.898), reversing an option the author had offered. "One element per concept" was refuted
  (57 of 109 entries sit one hop from another). 216 of 336 wrong-concept FP references fall in kinds the reference
  lists in *other* modules: the reference itself is inconsistent across modules.
- **KEY DECISION (rules need a basis outside the reference).** `ASSET_DEFINITION.md` adopted 2026-10-01. Each
  convention is tagged with its literature basis. A rule whose only support is a count from the reference may only be
  applied in code after generation, as a separately labelled row (DEF §3, §5).
- **Definition arm** (`ismd`): P 0.340, R 0.877; the transit rule was used in 0 of 378 concepts. Not adopted:
  "Fourth prompt arm whose exclusion sentence changed nothing."
- **Blind-agent prompt study** (Claude executors, prompts written from theory papers only): the best reaches about
  P 0.36 / R 0.6 (tuning 0.359 / 0.577, held-out 0.362 / 0.619). The gap to the reference is its conventions, not
  reasoning (REL; `blind_agent/REPORT.md`).

### Held-out pre-registration, 2026-10-01

- **KEY DECISION (held-out discipline).** `HELDOUT_PREREG.md` was written before any held-out run. It pins 18 files by
  sha; the reading script refuses to run if any pinned file changed or if the reading was already taken. One rule
  decides (R1: adopt majority vote + NONE + back-fill only if its precision gain over majority vote has a 95%
  interval above 0 and recall ≥ 0.83). It also states what is not blind: two conventions were checked on all 41
  modules early, so only filter *differences* are a clean test (HPR §4-5).
  - Lever terms: **MV** = keep an element listed in 2 of 3 runs; **NONE** = drop an element with no evidence path in
    the trace; **BF** = back-fill an input port whose value reaches a stored or computed element; **GUARD** = drop
    record fields never used in a condition.
- **Before the reading, GUARD was found overfitted** (REL, 05:36): about 70% of its in-sample gain is plain thinning
  (a random rule of equal strength gives 0.419 / 0.703). This reversed the earlier note that "the win is a
  post-generation guard filter". GUARD is never adopted.
- **Result, read once** (REL; AL2 §10): winner alone P 0.352, R 0.852; MV+NONE+BF **P 0.399, R 0.884**, gain over MV
  +0.049 [0.025, 0.080]: R1 passes, adopted. GUARD 0.446 / 0.801 against equal-strength random thinning
  0.393 / 0.707: logged correction, "weaker out of sample but NOT noise", still kept out of the headline.
  LAsset initial on the same modules: spec + RTL 0.734 / 0.862.
- **Like-for-like comparison fixed** (REL; DEF §6). The user confirmed which LAsset file is the RTL-only run:
  0.680 / 0.748 on tuning, 0.730 / 0.757 on held-out. For LAsset the spec adds mostly recall (+0.162 tuning,
  +0.105 held-out) and little precision (+0.057, +0.004).

### Traceability (cited occurrences) and the optimization loop, 2026-10-01 to 10-02

- **Traced arm `ist`** (2026-10-01): each element cites an occurrence ID and a map edge, checked by code. P 0.359,
  R 0.691, recall FAIL; 276 of 276 concepts cite map facts (the winner: 0 of 349). A post-pilot rule the author added
  broke the transport exclusion (98 of 112 transport references cited "via field"), logged as "my error" (REL).
- **`ist2`** (2026-10-02): two calls. Generation without the in-call questions, then a separate CIA labelling call
  that follows IEEE P3164's own question (the inherited confidentiality criterion was not P3164's and gave "no" on
  276 of 276 concepts) (REL; DEF §6). On gpt-5-mini: P 0.343, R 0.733; its citations verify 0.818, which misses its
  own pre-registered bar of 90% (LED §1, §4).
- **Prompt-optimization loop with Claude-agent executors** (2026-10-02; OPT). Fixed evaluation set and scorer; every
  executor's file access audited; a change kept only if F1 beats run noise.
  - v0 (the ist2 prompt): mean P 0.335, R 0.887. v1 (three edits from observed error patterns): mean of 3 runs
    **P 0.371, R 0.934, F1 0.531**.
  - v2: an edit (D) was written, then withdrawn after review: it contradicted the prompt's own definitions and had no
    basis outside reference counts. It moved to the evaluation layer as "R1a". The loop's rules were tightened to
    require a basis for every prompt edit, reversing a relaxation made earlier the same day.
  - v3: no edit beat noise; the loop stopped by its rule. The precision target (0.85) was not reached.
- **KEY DECISION (reject a rule that fits only the tuning set).** A held-out check was pre-registered before any
  held-out run of a loop version (HCP), and read once: v1 vs v0, precision +0.019 ("direction only, within noise"),
  recall +0.032. R1a removed 23 FPs and 8 true positives, and random thinning reached its precision in 24.8% of draws:
  "tuning fit", not adopted (OPT; DEF §3).
- **Final version on a stronger model** (gpt-5.4, run by the user): P 0.407, R 0.820 (3 runs), against the ist2
  prompt on the same model, 0.407 / 0.815 (2 runs). "The gain over gpt-5-mini is the model's; the loop's edits add
  nothing measurable on gpt-5.4." The pre-registered readings were labelled CONFOUNDED because the paired baseline is
  incomplete (API credits ran out) (OPT).

### False-positive diagnosis and the evidence layer on LAsset's lists, 2026-10-02

- **FP diagnosis from occurrence IDs and the map** (`fp_diagnosis.py`, `fault_reporter.py`; code only, the LLM part
  was never run) (OPT; LED §6). 94% of FP citations verify (true positives 99%): FPs are not misreadings of the RTL.
  All 21 relationship classes occur on both hits and FPs. Hit vs FP from relationship classes: AUC 0.762 in-sample,
  0.629 on a module left out (0.5 = chance). Rules learnt per cluster carry partly to held-out (P 0.329 → 0.478,
  R 0.931 → 0.640). 69% of FPs sit in concepts with no reference element. This replaced the author's earlier
  one-line reading "FPs cannot be controlled".
- **Contribution assessment** (LED, SKP). Every figure re-derived; the skeptical review graded the author's own
  draft claims. "Every reported asset is linked to an RTL occurrence and a relationship record that code verifies":
  WRONG (0.818 of cited rows verify on gpt-5-mini). The error analysis "with LLM explanations checked by code":
  WRONG (the LLM part never ran). "First asset-identification method with per-decision source-level grounding":
  OVERSTATED. Verdict: "incremental", an evidence and error-analysis contribution rather than an accuracy one. It
  named one missing test: apply the map to LAsset's own lists.
- **KEY DECISION (pre-register a test expected to fail, and report it).** The evidence layer applied to LAsset's
  published lists, with no model call (LLP).
  - Design v1 was replaced after a tuning-only review showed it measured version drift and "the element is used".
  - Before the held-out reading, the tuning model was already below chance (AUC 0.448), so H1 was expected to fail
    and H2 to be untestable. The primary list was not switched to the better-looking spec+RTL list, because "that
    would choose the test by its result" (LLP §4).
  - Result (LLR): H1 AUC 0.639, 97.5% interval [0.495, 0.768], does not hold; H2 not testable. Claim supported:
    **"audit trail only"**. The map traces every LAsset item that exists in this RTL version to its relationships
    (99% of hits and 96% of FPs have a traced use), but this evidence does not separate LAsset's hits from its false
    positives.

### Results on the 41 modules and the false-positive trace, 2026-10-02 (NB-final)

- **Held-out generation on gpt-5.4, run once credits were topped up**: 26 modules x 3 runs, 78 module calls, 0
  validation issues (`runs/assets_heldout26_m7e194es0opt1_g54_r*/_validation.json`), about 75 min (file times);
  6,776,616 input and 1,938,111 output tokens (`runs/assets_heldout26_m7e194es0opt1_g54_r*/_usage.json`); at most
  $46.01 at the gpt-5.4 list price of $2.50 / $15.00 per 1M input / output tokens on 2026-10-02 *(derived)*; cached
  input bills less.
- **The final prompt on all 41 modules** (300 entries; NB-final): P 0.394 / R 0.856 against LAsset RTL-only
  0.711 / 0.753; difference P -0.316 [-0.392, -0.232], R +0.102 [+0.037, +0.167] (module bootstrap, 95%). Held-out
  alone: P 0.388 / R 0.877. Precision is close to tuning (0.406 pooled; run mean 0.407); recall is higher (0.820). The
  41 RTL files are listed in `data/LASSET_41_MODULES.csv`. The Claude-executed runs of the same prompt (0.343 / 0.932)
  are kept as a check.
- **Definitions corrected after an independent verifier**, beside the 2026-10-02 figures above, not inside them: the
  "21 relationship classes" included 8 element attributes (13 relationship classes; all 13 occur on both hits and
  FPs); "FPs in concepts with no reference element" counted every asset, hits included, under its first concept
  only (fp_diagnosis D5: 237/399, 59%; OPT). Counting every concept: 218/399 (55%) on the 15 tuning modules and
  gpt-5.4 runs; 525/1183 (44%) on all 41.
- **KEY DECISION (test a reading on more data, and keep it when it survives).** On all 41 modules the unseen-module AUC
  is higher than on 15 (gpt-5.4: leave-one-module-out 0.805 over 41, against 0.644 on the 15 tuning modules alone). A
  first draft of the notebook read this as showing that the separating differences do not weaken on unseen modules,
  and withdrew the earlier reading. An independent claim audit split the figure by module set: on the tuning modules
  the AUC still falls from in-sample to unseen even with all 40 other modules to learn from (0.776 -> 0.678); the
  held-out modules separate better and lose less (0.911 -> 0.875). The withdrawal was reverted the same day.
- **The test named in advance** (rules that raise held-out precision substantially without a large recall loss) was
  then run on gpt-5.4's own held-out runs. Tuning rules raise held-out precision 0.388 -> 0.545 (0/2000 random removals
  reach it), but recall falls 0.877 -> 0.598, and both stay below LAsset RTL-only. The test is not met, so the reading
  that rules built from the structure cannot close the gap without losing recall stands.
- *Reading:* on the held-out modules, part of the gap is the reference's role preference: it lists internal state at
  0.011 of its entries (0.082 on the tuning modules), while the model lists it at 0.159 of its list; leaving the role
  out (in-sample) gives held-out P 0.459 at R 0.866. The rest is a choice among elements that the relationship
  profiles separate only partly.
- **Module portraits from the two structures** (`final/module_insights.py`): registers written from an input (192;
  116 from a write-data port), internal write guards such as `ctrl.lock`, reset coverage and exported state, for all
  41 modules.
- **The adopted code levers on gpt-5.4 (2026-10-03; not pre-registered for this model).** The frozen MV+NONE+BF
  (`assetgen_meta/post_levers.py`, unchanged) on the final gpt-5.4 runs, as a separately labelled row (FINAL_NOTEBOOK
  section 6; `final/levers41.py`, whose self-test first reproduces the 17 recorded tuning stacks, the stored held-out
  reading and the gpt-5.4 base rows). Held-out: P 0.394 -> 0.405, R 0.884 -> 0.847 against MV alone; precision
  +0.011 [-0.004, +0.029], recall -0.037 [-0.063, -0.015] (module bootstrap, 10,000 resamples, seed 0). The
  pre-registered rule R1 would not pass for this model: recall clears 0.83 (0.847), but the precision interval includes
  zero, and a gain the size of gpt-5-mini's +0.049 lies outside it. The headline rows stay without levers. gpt-5.4
  writes a code line out for far fewer listings (held-out 18.0% of 1,281 listings over 3 runs; gpt-5-mini 74.7% of
  1,374), so NONE rests mostly on the map's check of each label. A hand check found a weakness of the frozen NONE rule:
  it confirms "stores" only for map storage class "edge", so a clocked register that also has a constant assignment
  (storage "mixed", e.g. the hard-wired x0 entry `reg_file(0)`, `data/RTL_heldout/neorv32_cpu_regfile.vhd`:117) is
  dropped. On gpt-5.4 held-out, 51 of NONE's 97 drops are such "stores" elements, and 16 of its 56 "stores" drops are
  reference hits. The rule stays as frozen; a changed rule would be a new, untested lever.

---

## The decisions that best show research judgement

1. **Pre-registration from day one of the study** (2026-08-03): `Expect:` and a decision rule before every run;
   wrong predictions recorded; a registered block corrected beside, never inside (AL1 A-02, 2026-08-05).
2. **No answers in prompts** (2026-08-08): the `ctrl_i` leak found and removed; the leak test itself was corrected
   the same day when v2 was built (`clk_i`/`rstn_i`), then enforced in code (AL1 L-1; AL2 §3).
3. **The recall guard as a table-side decision rule, never a regenerate-until-better loop** (2026-08-08; AL2 §2).
4. **Measure the instrument before trusting its counts** (2026-08-21 to 08-22): a replicate showed an "effort
   effect" was noise (VER V-1).
5. **Code where there is one right answer** (2026-09-21 to 09-30): structure chains and relationships moved from the
   LLM to code after measurement, with the position change logged (NB-meta cells 76, 82; REL).
6. **Held-out discipline** (2026-09-21 to 10-02): held-out RTL obtained; two pre-registrations with pinned files,
   read once (HPR; HCP).
7. **Rejecting overfitted rules** (2026-10-01 to 10-02): GUARD never adopted; R1a rejected after failing held-out;
   prompt rules need a basis outside the reference (DEF §3, §5; OPT).
8. **Correcting earlier claims in the open:** P-2 reinstated (08-08), the T-1 "prompt failure" that was our bug
   (08-07), the F1 claim (08-08), the relation-writer position (09-29/30), GUARD "overfitted" softened to "weaker
   out of sample but not noise" (10-01), "FPs cannot be controlled" (10-02), and the skeptical review of the author's
   own claims (10-02).

---

## Could not date or verify

- **Late-July first run and the 163-FP root-cause pass:** numbers are in TG (undated). The date comes only from a
  session note (2026-07-25/26), not a repo file.
- **The "~20% cap" and "`ctrl.*` eleven times" lessons:** recorded in AL1 without a date; placed in July because AL1
  opened on 2026-08-02 and treats them as earlier.
- **P-1 result:** AL1's `Got:` line is empty; the null result is taken from HO and AL2 §3.
- **L-1 (`v01c6p1p2d`) was never run on its own;** it was folded into v2, so whether the leak did work is unknown
  (AL2 §9).
- **API triage ablation (P0-P8, 2026-08-18):** built, never run (empty results folders). Parser v7: built, never run.
- **Step 2 (2026-09-21) result and the `i01b` / `ismp` scores:** not in any log; re-derived in this session from
  stored runs (`step2/apply_rules.py`; `assetgen_meta/hand_arms/score_hand_arm.py`), with no API call. Both
  scripts reproduce the logged numbers for the winner (0.344 / 0.847) and the seed (0.379 / 0.787).
- **The 2026-09-18 change of direction** (use a code-built relation map to remove false positives) is recorded only
  in session notes; S2 refers to "the roadmap" but the roadmap itself is not in the repo.
- **In-log inconsistencies:** AL2 gives v2 as 0.251 / 0.925 (§5) and 0.250 / 0.930 (C1 table); NB-meta gives run 6's
  remaining structure errors as 21 (cell 78) and 22 (cell 82). LED lists further differences between on-disk
  figures and today's re-runs (e.g. `ist` citations 0.944 on disk vs 0.812 with today's checker, after a rule change).
- **Gold set for the relation map** was written by an LLM (gpt-6-astra), not a human, and covers tuning modules
  only; the held-out map has no accuracy measurement (LED §5).
- **Dates for September and October** come from dated log entries and file modification times; that work was first
  committed to git on 2026-10-02.
