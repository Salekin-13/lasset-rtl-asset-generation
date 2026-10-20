# Recall study, 2 to 8 August 2026: ablation log, short form

The first prompt study of the LAsset replication (Algorithm 1 line 5, asset generation) on NEORV32. Objective: recall,
because LAsset's refinement stage only removes (its own figures: precision +0.083, recall -0.026), so recall out of
generation caps the whole pipeline. The full record is `logs/ABLATION_LOG.md` (AL1); from A-02 on, each arm's `Expect:`
and decision rule were written into it before the run (A-00 had none, A-01's were agreed in discussion). The hand-off to
the precision study is `logs/V02_HANDOFF.md` (HO).

Every number below was re-derived on 2026-10-20 from the stored runs (`runs/assets_tuning18_<version>_r<k>/`, local,
not published; two abandoned P-2 folders, r3 and r4, hold no module and are excluded) by
`experiments/01_prompt_baselines/notebooks/recall_ablation_log.ipynb`, with the strict scorer (`src/eval_assets.py`, metric M-2: exact name match, or
a whole record against one of its fields; a name counted once per declaring entity). A figure marked (AL1) or (HO)
comes from the log only: judge readings, oracles, and counts whose inputs are gone. Precision = hits / listed elements;
recall = hits / reference entries; both are the mean over runs of the per-run figure (the README draft pools runs,
which moves four cells by 0.001). Paired deltas pair the 15 modules, with a 95% bootstrap interval and the count of
modules better / worse; an interval that includes zero is a null at this sample size.

## Prompt technique and structure

- **Technique.** Few-shot prompting (ICL, in-context learning: worked examples inside the prompt), as LAsset does. One
  call per module, gpt-5-mini at reasoning effort `high`, JSON output: a list of assets, each an element name with its
  entity, objective and justification; from v01c4 a `ConceptualAssets` array first. The core states IEEE P3164's
  conceptual-and-structural analysis: four questions per element (Confidentiality, Integrity, Availability, Undermine),
  then a binding of each conceptual asset to the design elements that store, carry, generate or gate it. Only primary
  assets are asked for. Every listed asset must name one element of the closed set (the ports and signals extracted
  from the RTL by regex), so each listing is checkable against a real name.
- **System prompt = core + ICL block.** Core sections: INPUTS, DEFINITIONS, METHOD (STEP 1 conceptual assets, STEP 2
  structural binding), RULES, OUTPUT CONTRACT; 4,364 chars at v0, 7,249 at v01c6. The ICL block: at v0, P3164's own
  three worked analyses (GPIO, noise generator, AES), not in the task's format, 8,460 chars; from v01, two worked
  input-reasoning-output triples from open IPs outside NEORV32, `omsp_gpio` (labels from Nath & Tan's dataset) and
  `tiny_aes`, in the task's exact input and output shape, 97,049 chars; from v01c5, the same two with a
  `ConceptualAssets` array. Each run's `_run_meta.json` carries the prompt's SHA-256; recomposed today from
  `src/prompts.py` and the `src/icl_examples_*` modules, all ten run versions match byte for byte.
- **Inputs (the user message).** (1) a technical summary from LAsset's SpecRAG (datasheet chunks of 1,000 chars,
  overlap 200, top 20, `text-embedding-ada-002`, AL1 C-02; generated once, reused by every arm); (2) the parsed I/O
  ports and (3) the parsed internal signals as JSON, each element with an LLM-written `function` string; (4) the RTL
  with comments stripped. Over the 18 modules: summary 11.8%, parsed lists 51.3%, RTL 36.9% of the characters; the
  parsed lists are 58% once the summary is gone. On the watchdog: 15,112 chars with all four blocks, 11,043 without
  the summary, 4,943 RTL only. The closed set over the 15 scored modules: 1,572 distinct names (1,641 entries, a name
  once per entity); 111 of them are reference entries (7.1%); 959 entries are fields of record ports.
- **Scoring.** 18 modules run, 15 scored (`boot_rom`, `fifo` and `package` have no reference entries and were kept as
  negative controls). Reference: LAsset's manual list, 111 entries on the 15. Two entries cannot exist in this RTL
  revision (`cache`: `inval_i`, `cache_o.cmd_dir`), so recall tops out at 0.982 (AL1 C-03). Runs: three per arm; five
  for v01c4 to v01c6p1 (v01c2 and v01c3 were extended to five after their decisions); P-2 three; the control two.
  Per-class recall (port, signal, signal-field) is the primary reading from A-01 on.

## Fixed before the study (AL1 section 2, plus two lessons from before it)

- The closed set is built by code, not the LLM; the model is told to add none and drop none.
- SpecRAG at the paper's parameters, summaries made once.
- RTL comments stripped for the asset stage only (the closed set is identical either way).
- No post-filter between generation and scoring: the port-field rule as a filter would delete a hit (`ctrl_i` in
  `cpu_pmp`, listed as `ctrl_i.csr_wdata`); as an instruction it redirects. Carried to A-03.
- `Got:` pasted from `ablate()`, never retyped (one slip logged as R-03; P-1's `Got:` was left empty).
- A numeric cap ("stop at ~20% of the closed set") and a checklist of signal types had each failed in earlier,
  unlogged trials (AL1, undated): a cap becomes a quota, a list becomes a generator. So no number, proportion or
  threshold enters a prompt.

## Results

| version (arm) | change | P / R (runs) | listed | union R | decision |
|---|---|---|---|---|---|
| v0 (A-00) | first prompt | 0.300 / 0.553 (3) | 205 | 0.685 | base; noise floor sd 0.019 |
| v01 (A-01) | two worked case studies | 0.288 / 0.607 (3) | 235 | 0.748 | prediction met: port +0.18, signal -0.16 |
| v01c2 (A-02) | judge an element by its role, not by where it sits | 0.277 / 0.744 (5) | 297 | 0.892 | pass, promoted |
| v01c3 (A-03) | record ports named whole | 0.318 / 0.784 (5) | 274 | 0.928 | pass, promoted |
| v01r (A-03 control) | A-03 on the v0 core | 0.331 / 0.626 (2) | 210 | 0.703 | precision up as in the arm; port recall up, so no suppression |
| v01c4 (T-1) | STEP 1 written out | 0.267 / 0.845 (5) | 352 | 0.928 | diagnostic; concepts lost by our code |
| v01c5 (T-1b) | examples show the concepts | 0.285 / 0.849 (5) | 331 | 0.928 | null; kept |
| v01c6 (A-08) | after listing a concept's elements, read the closed set once more for it | 0.229 / 0.881 (5) | 428 | 0.955 | pass, promoted |
| v01c6p1 (P-1) | summary removed | 0.210 / 0.897 (5) | 476 | 0.955 | null, promoted |
| v01c6p1p2 (P-2) | parsed lists removed | 0.243 / 0.886 (3) | 404 | 0.937 | pass, promoted; end of study |
| v01c6p1p2d (L-1) | leaked names replaced | built, not run | | | folded into v2 |
| LAsset line 5 (published) | | 0.737 / 0.910 (1) | 137 | | |

T-1b is this note's label for the second T-1 hop (v01c4 to v01c5). Union R = recall of everything any run of the
version produced, at the version's own run count (v01c2 to v01c6p1 over 5; v0, v01 and v01c6p1p2 over 3; v01r over
2). Only two reference entries were never produced by any run of any version: the two unreachable ones in `cache`.

## Arms

### A-00, v0: noise floor
No pass rule (the first arm). Got: recall sd 0.019, F1 sd 0.010 over 3 runs; recall 0.553; port 0.326, signal 0.771,
signal-field 0.688. The model listed internal state and missed two thirds of the ports. Reading: repeats are not the
limit, modules are. Paired aggregate-recall intervals run 0.15 to 0.23 wide at 15 modules (AL1 wrote "about ±0.14"),
so effects under about 0.10 read as inconclusive. Next: A-01.

### A-01, v01: worked case studies (ICL block, 8,460 to 97,049 chars)
Before the run (agreed in discussion, no pass rule). Port recall rises: the examples bind all 18 of their assets to
ports. Listed elements rise and precision falls. Discriminator: if the gain lands only in modules whose summaries
already name their port assets, SpecRAG is the constraint. The earlier v1 examples were dropped unrun: their
identifiers were invented.
Got: port recall +0.181 [+0.048, +0.302], 9 modules better, 1 worse; signal recall -0.157 [-0.229, -0.086], 0 better,
6 worse; aggregate +0.049 [-0.061, +0.166], a null that hid two real effects; port-field false positives 19 to 51 per
run. Modules whose summaries named none of their port assets went 0.355 to 0.645 (AL1), so SpecRAG is not the
constraint. Prediction met; kept as baseline. A-01x (AL1): every labelled example IP is 75 to 100% ports and NEORV32's
reference is 42% port / 29% signal / 28% signal-field, so no example can fix the signal loss. Next: instruction (A-02).

### A-02, v01c2: "role, not location" (core +1,366 chars)
Before the run: signal recall recovers toward v0's 0.771; port recall holds near 0.589 (a guard); listed elements up
modestly, precision flat. Rule: signal up and port holds, promote; signal up and port down, oscillation, so the
example channel (a third example set, v03) is the only lever left; signal flat, instruction cannot override a
demonstration.
Got (3 runs): signal +0.106 [+0.047, +0.165], 6 better, 0 worse; port +0.262 [+0.110, +0.414], 9 better, 1 worse (the
guard was set too low: the insertion asks both questions); aggregate +0.162 [+0.083, +0.232], 13 better, 1 worse;
precision -0.001; listed 235 to 306 (AL1: 304), not modest. Pass; promoted. Side effect: four names with the entity
prefixed in one run (AL1), a cost to this arm. Six modules at port recall 1.0 (AL1), so the port lever is nearly
spent. Port-field false positives 74 per run (AL1: 73), the largest excess over LAsset's list (AL1: port-field 73
against signal-field 64). Next: A-03.

### A-03, v01c3: record-typed ports named whole (core +340 chars; two edits, one proposition)
Before the run (AL1): an oracle on v01c2's own output (rewrite each port field to its record, dedup) gives precision
0.286 to 0.338 with recall unchanged, so the arm is precision-only and its guard is on recall. The 73 port-field
listings per run are 34 records, one of them in the reference, so the rule renames rather than removes. A symmetric
clause for internal records was dropped: the model never emitted a bare internal record (0 of 90 module-runs). The
core's own naming example was a port field (`host_req_i.stb`) and was swapped out in the same arm. Rule: precision up
and port recall at least 0.80 and aggregate recall not down, promote; precision up and port recall down, revert;
flat, a post-filter as a declared deviation. Control v01r: the same two edits on the v0 core, 2 runs, directional
only, run at the same time so both arms met the same model.
Got (3 runs each). Precision +0.042 [+0.006, +0.077], 11 better, 4 worse; F1 +0.046 [+0.002, +0.087]. Port-field false
positives 74.0 to 1.7 per run (AL1: 72.7 to 1.7), the best-followed rule of the study. Port recall 0.801 against the
0.80 floor (per run 0.745, 0.766, 0.894); aggregate +0.008. Signal-field false positives 84.3 to 92.3 (AL1: 83 to
92): the fence sentence was not neutral. Control: precision +0.060, the same sign as the arm; port recall +0.048,
opposite to the arm's -0.037, which rules out port suppression. Pass by 0.001 on the guard; promoted. A rename, not a
removal: whole-port false positives 19.7 to 54.7 (AL1: 19 to 55). Both versions were extended to 5 runs on 08-06, the
day the promotion was logged (the arm's three runs were on 08-05; v01c3's run times are rebuilt from file times, the
originals were overwritten): precision +0.050 [+0.021, +0.080], F1 +0.060
[+0.027, +0.091], port recall paired -0.009 [-0.101, +0.086], mean 0.796, under the floor by 0.004 (runs 4 and 5:
0.702, 0.872). The decision stands on the 3-run reading and the control's sign. A-04 (drop port fields from the closed
set at the parsing stage) was superseded by this result and never run. Next: T-1.

### T-1, v01c4 and v01c5: are misses never conceived, or conceived and not bound? (diagnostic, not an arm)
Before the run: the output contract changes (STEP 1 written out as a `ConceptualAssets` array with an id per asset),
so the recall delta is confounded and is never quoted as a result. Registered checks (AL1): the array present; 1.5 to
6 elements per concept; at least 4 concepts per module.
v01c4: the array was in 0 of 90 files, our run loop's fault (Corrections); 90 calls lost. v01c5 (examples show the
array): all three checks pass: 89 of 90 files; 6.24 concepts per module; 3.54 elements per concept (AL1's diagnostic
read 3.63). The judge (an LLM call that reads each miss and says whether one of the model's own concepts covers it)
agreed with the model's own links on found entries at 0.97 exact, 1.00 any (AL1). Split (AL1): 82.1% of misses
conceived but unbound, 14.3% objective absent from the concept list, 3.6% judge finds no concept; 82 to 85% over two
judge runs; every strong "never conceived" case is Availability. v01c4 to v01c5: recall +0.004 [-0.024, +0.033], null
on every metric; kept. Open: the judge's permissiveness is not bounded (a mismatched-module control was never run), so
82% is an upper bound. Next: A-08 (completeness within a concept); A-09 (Availability) was named and never built.

### A-08, v01c6: per-concept closure sweep (core +550 chars)
Before the run: the primary reading is the union over 5 runs, stuck at 0.928 (103 hits) for v01c3, v01c4 and v01c5;
it must rise. Recall +0.02 to +0.06; precision -0.02 to -0.04; guard: the "never conceived" fraction unchanged; stop
clause: precision falls by more than 0.05. Rule: union up and recall up, promote; recall up with the union flat,
variance only, do not promote on the mean; flat, a verification pass cannot be induced by text.
Got (5 runs): union 0.928 to 0.955, 103 to 106 hits; two of the new entries (`cpu` `alu_add`, `alu_res`) had been
produced by no run of the three plateau versions, and AL1 names `bus` `stb` as a third; recall +0.027 [+0.009,
+0.046], 8 better, 1 worse; precision -0.038 [-0.057, -0.021], 2 better, 13 worse (the raw mean fell 0.056; the stop
clause had not said which figure); elements per concept 3.54 to 4.49 with concepts per module 6.24 to 6.36, so
concepts got fuller, not more numerous; the "never conceived" fraction moved 14.3 to 12.1% (AL1), a mild guard
violation; port-field false positives 2.2 to 9.2, partly undoing A-03. Pass; promoted. Precision 0.229 against
LAsset's 0.737 is now the limiting problem. Next: the input ablations P-1, P-2' and P-3, registered together; P-2 was
rejected at that point and reinstated on 08-08.

### P-1, v01c6p1: spec summary removed (core -173 chars; summary block; examples -5,137 chars)
Before the run: precision -0.02 to +0.03, leaning null (basis in AL1); guard: recall not down by more than 0.03.
Rule: precision up by more than 0.03, stage 3 is the lever and every summary would have to be regenerated; null,
proceed to P-3; recall down, the summary stays. The examples' two reasoning lines that cited the summary had the
citation deleted, not rewritten.
Got (5 runs): precision -0.011 [-0.026, +0.008]; recall +0.016 [-0.014, +0.050]; F1 -0.014 [-0.032, +0.006]; listed
428 to 476. Null; promoted. Next: P-2, reinstated on 08-08 in place of P-3, which was never built.

### P-2, v01c6p1p2: parsed lists removed, the model reads the declarations from the RTL (user message -58%)
Rejected at registration, reinstated 08-08: the closed set was re-sourced to the RTL's own declarations in three core
edits, so every earlier rule stays as written (Corrections). One confound closed first: the loop's
validate-and-regenerate retry would pick the sample closer to the withheld list, so this version reports and never
regenerates, and `_validation.json` is written per run. Predictions: recall -0.03 to -0.12; listed 260 to 360;
precision 0 to +0.05; 3 to 10% of names outside the parsed set. Rule: recall within 0.03 and listed down, promote
(the parsing stage is overhead at generation); recall down by more, the closed set is load-bearing and P-2' (keep the
names, drop `function`) follows; never promote on F1. Not a LAsset configuration: line 5 always receives the parsed
elements.
Got (3 runs against 5): recall -0.020 [-0.086, +0.039], 5 better, 5 worse; listed 476 to 404; precision +0.017
[-0.013, +0.050]; 187 names outside the parsed set over 18 modules, every one declared in the RTL (176 in `package`,
whose parsed set is empty), none invented; on the 15 scored modules 8 of 1,212 listed names (0.7%; AL1: 0.5%). Three
of four predictions wrong. Costs: union over 3 runs 0.937 against 0.950 (range 0.946 to 0.955) for the baseline's ten
3-run subsets; recall sd 0.032 against 0.015 (sample sd; AL1: 0.026 against 0.012). Pass; promoted, with the lower ceiling recorded
as the cost. Next: L-1, built and not run; the study closed on 08-08. P-2' and P-3 (drop the RTL) were registered and
never built.

### L-1, v01c6p1p2d: evaluation-set identifiers out of the prompt (core +5 chars)
Found 08-08 (AL1): the A-03 rule quotes `ctrl_i`, a reference answer in 10 of the 41 modules, 9 of them in the later
held-out set; worth at most 0.009 recall on the tuning set (1 of 111), disqualifying for a held-out run. Not a
confound for P-1 or P-2 (in baseline and arm alike). A new version rather than an edit, so no stored run's prompt
hash changes. Expect: null; rule: null, it becomes the baseline. Standing rule: no identifier from the 41 modules
enters a prompt (later enforced by code). Never run as an arm: folded into the v2 baseline of the precision study,
whose bundled delta is not attributable.

## Where the study stopped

- Last promoted version: v01c6p1p2, precision 0.243, recall 0.886, 404 listed per run, against LAsset's line 5 at
  0.737 / 0.910 with 137. Comparable recall by listing three times as much (HO).
- Registered and not run: L-1 (into v2), P-2', P-3. Named only: A-09; v02 and v03 (alternative example sets, A-01 and
  A-02). Superseded: A-04.
- Noted at the close (HO): five prompt arms were tuned on the same 15 modules, three of them (A-02, A-03, A-08)
  designed after reading misses there, so a held-out set was needed; about half of the false positives are elements
  LAsset lists as secondary assets (52.9% at v01c6, AL1), a structural share no arm moved, deferred.
- Hand-off 2026-08-08: objective switched to precision with a recall guard (`logs/ABLATION_LOG_V2.md`).

## Corrections kept in the log

- v01c4: "the examples overrode the contract" was our run loop's result line keeping two keys of each reply and
  dropping the `ConceptualAssets` array before it reached disk.
- A-02: the stated basis of a prediction was misread; corrected beside the registered text, not inside it.
- P-2: a confident rejection rested on one false premise (that the closed set is the JSON blocks); re-check the
  premise, not the reasoning on it.
- Metric M-2 (08-03): same-name elements in two entities of one file had been collapsed; this alone made the reference
  total 301 instead of 302 (AL1). Re-scored, not re-run.
- Near matches (a record against one of its fields, either way) were 0.4% of hits at v01c6; every version-to-version
  gain survives exact-only matching (AL1; audited 08-07, metric unchanged).
- "The residual is bus plumbing, 33 of 34 records" sized A-03, not the remaining false positives: on v01c3, bus
  records are 16% of them (AL1, 3 runs); signal-field listings (92 per run at 3 runs, AL1; 90 over 5) are the largest
  block, against LAsset's 19.
- A baseline promotion written in prose was not applied in the notebook; caught before P-1. Propagate it in the same
  edit.

## Re-derived against logged

Every paired delta, mean, union recall and false-positive count above reproduces AL1 or HO at the matched run count,
with these differences: one bootstrap bound (A-03 precision, +0.005 in AL1, +0.006 here); v01c2's 3-run baseline
figures (listed 306 and 219 false positives per run here, 304 and 217 in AL1); run-to-run sd (sample sd here; AL1 and
HO run 10 to 20% lower, consistent with an n denominator); the P-2 absent rate on the scored modules (0.7% here, 0.5%
in AL1); elements per concept (3.54 and 4.49 here over every concept of the 15 scored modules; 3.63 and 4.62 in AL1,
whose diagnostic in `src/diagnose_step1.py` counted on a basis AL1 does not state, not traced); the closed-set size
(AL1's 1,572 is distinct names per module, 1,641 counts a name once per entity); block shares (AL1's 11 / 58 / 31% was
a single 31,389-char message whose module it does not name; over 18 modules it is 11.8 / 51.3 / 36.9%, and the parsed
lists are 58% of the message once the summary is gone).
