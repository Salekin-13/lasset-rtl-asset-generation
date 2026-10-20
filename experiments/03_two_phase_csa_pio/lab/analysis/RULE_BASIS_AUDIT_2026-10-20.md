# Rule-basis audit of the final prompt two_phase_p1o_first (2026-10-20)

Question answered: which rules of the final prompt rest on what the reference lists rather than on theory, beyond the three decisions the README names; and how general the rules are.

Method. Every column-0 block of phase1.md lines 21-176 and phase2.md lines 34-150 of `prompts/two_phase_p1o_first/` was listed by a script (scratchpad trace_rules.py: 83 blocks; the five unindented lines of the debug bar merged into one; Phase 2 copies merged with their Phase 1 rule; headers dropped). Origin = the first version of the chain v1 -> v2 -> v2a -> v3 -> v4 -> v4a -> v5 -> v5f -> v5g -> v6 -> v6d -> v7 -> v8 -> v9 -> v9f -> v9g -> v9h -> v9i -> v9j -> v9n_place -> p1o_first whose prompt files contain the block head (self-test on six hand-read blocks: PASS). Basis = the label recorded for the rule in its version README, the rule record (RULES_V6_APPENDIX.md, RULES_FROM_V7.md, new_rules/meta_v9k.json, meta_v9h.json), PLAN_V9K.md, PLAN_ISOLATE_CLUSTER_ORDER.md section 11, or DECISION_LOG.md. Scope = modules of the 41 whose rtl.txt matches a construct pattern (grep over inputs/v1; exact unless marked).

Classes. C = labelled "user decision / reference convention / no published basis", or the recorded basis is a count of reference against non-reference elements. F = drafted in a failure analysis against the reference (false-positive or miss tables) with a principle basis stated (the prompt's definitions or a source). T = a published source cited for this specific rule. D = the prompt's own definitions, written before any run. P = procedure.

| id | rule | where | origin | class | basis as logged | README decision | scope (modules of 41) | note |
|---|---|---|---|---|---|---|---|---|
| R02 | Describe by information, not element name | P1:22 | v1 | D | the prompt's own 2.4 (P3164 conceptual vs structural) | - | - |  |
| R03 | Precedence | P1:23 | v6 | P | procedure: how bars and keeps override each other (v6 integration; D57 wording) | - | - | written after bars were ignored in runs; no element content |
| R04 | Reading a rule | P1:24; P2:35 | v9f | P | procedure (v10 diagnosis E3 merged procedure) | - | - |  |
| R05-R09 | Debug module registers | P1:25-29 | p1o_first | C | "user decision 2026-10-19: reference convention" (in the rule text itself; D95, D103) | 3 | 2 (debug_dm, debug_dtm; scope names a debug module or debug transport) | Phase 1 only; D95 pre-registered it as a reference-convention bar |
| R10 | Clocks and resets | P1:30 | v2 | C | v2 README A1: "None published; user decision 2026-10-12"; v5 R7b "B: None published" | 1 | - (every module has clock and reset) | ASSET_DEFINITION rows 61-62 kept this as an evaluation-layer convention; v2 moved it into the prompt |
| R11 | Build-time values | P1:31 | v2 | F | v2 A2: rubric mechanism (no run-time element can change it); v5 U11 restriction = "U: user decision, reference convention" | 2 | - | U11 part only |
| R12 | Pacing pulses | P1:32-36; P2:40-44 | v2 | C | v2 A3: step 3; the tick-input clause v5 R2b "B: None published; user decision 2026-10-12"; v11r3 rewording "principle" | 2 | - | held-out diagnosis: pwm clkgen_i lost to this rule |
| R13 | Forwarded transactions | P1:37 | v2 | F | v2 A4: LAsset p2 (buses carrying a primary's data are secondary); v6 CX6.U13 relayed-data clause = "U"; v9 narrowing drafted from held-out module xbus | 2 | 25 (modules with bus_req_t/bus_rsp_t ports) | the v9 clause was fitted to one held-out module (xbus 27 -> 9 finds at v2) |
| R14 | Forwarded-access stages | P1:38-42; P2:77-81 | v9i | F | G3 "theory": 2.6 carrier clause; drafted from 24 consistent debug FPs, bars 5 of them | none | 2 (debug_dtm, debug_dm: test or debug access port) |  |
| R15 | Second copies | P1:43 | v6 | F | P11.1 carrier (LAsset p2 / SAIF p2 via ASSET_DEFINITION 58-59); drafted from debug_dtm slice FPs | none | - |  |
| R16 | Bus handshake copies | P1:44 | v2 | F | v2 A5: step 3 + constant mechanism; v6 CX4.TF1 extension to one-bit transaction flags = "U" | 2 | 25 (bus record ports) | CX4.TF1 part |
| R17 | Response merges and re-timings | P1:45-49; P2:86-90 | v9i | F | G8 "theory": 2.6 carrier; drafted from 7 consistent bus FPs, bars 6 | none | 4 (units with both request and response record ports judged by hand: bus, xbus, cache, cpu_lsu; lower bound not measured) |  |
| R18 | Working values | P1:50 | v2 | F | v2 A6: step 3; LAsset p2; v5 R3 "A": P3164 3.1.2 p10 | none | - | two wordings were retracted because they removed correct finds (v2 README) |
| R19 | Slices | P1:51 | v6 | F | P11.4 carrier (LAsset p2 / SAIF p2); drafted from cache address-slice FPs | none | - |  |
| R20 | Hand-offs | P1:52 | v3 | F | v5 K2 "A": SA-EDI Table 2 via ASSET_DEFINITION row 55; v6 NC.K2S sharpening from misses | none | - | keep rule written to recover misses (v3 scope gaps; v6 recall item) |
| R21 | Decided-on instance outputs | P1:53 | v8 | F | v8 B1: "the prompt's own definitions" (2.6 outward clause); from the v7 failure analysis | none | 1 element in the 41 closed sets (v8 README: conflict_scan) | v8 README itself: "may not generalise" |
| R22 | Held outcomes, addresses and settings | P1:54 | v8 | F | v8 R6: "the prompt's own definitions"; from the v7 failure analysis | none | - |  |
| R23 | Instance-driven records | P1:55 | v5 | C | v5 U6 -> v6 CX3.U6p: "user decision, reference convention, to raise precision" | 2 | 1 (cpu wrapper; records driven whole by one instance into others) |  |
| R24 | Register read-back | P1:56 | v5 | F | v5 K1 "A": P3164 3.2.3 p15 (AES status registers); v6 CX8.K1s sharpening = "split label" | 2 | - | keep rule; CX8.K1s part convention-labelled |
| R25-R27 | Port buffers (a) (b) (c) | P1:57-72; P2:45-52 | v5 | C | v5 U2 "U"; (b) v8 R3 own definitions; (c) v6 P11.3 carrier; v11r drafter: "partly a reference convention" | 2 | 12 (modules whose RTL mentions fifo) | held-out diagnosis: slink handshakes and ipb flags lost to it before v9h |
| R28 | Sequencing state (+3 sub-rules) | P1:73-88; P2:53-67 | v6 | C | v5 U3 Serial engines "U" -> v6 CX2.U3b "U" -> v7 narrowing -> v8 R2 -> v11r3 rewording | 2 | - | v2 README had REJECTED the same idea (B3 Sequencers) as "contradicts step 2"; admitted in v5/v6 under the 12 Oct decision |
| R29 | Serial shift registers | P1:89; P2:121 | v6 | F | P11.2 carrier (LAsset p2 / SAIF p2); from 4 consistent FPs (spi, twi, uart) | none | 7 (serial units) |  |
| R30 | Buffer and engine status bits | P1:90 | v6 | C | v6 CX9-U "user decision, reference convention"; E1 gloss fix 2026-10-16 | 2 | - | v2 README had REJECTED B5 Buffer status: "The reference keeps one buffer's fill status" |
| R31 | Port options | P1:91 | v6 | C | v6 CX7.U1b "user decision, reference convention" (replaces v5 U1); v6 rules file: "the reference's convention, not a property of the RTL" | 2 | - |  |
| R32 | Cached copies | P1:92 | v5 | C | v5 U5 "U" | 2 | 1 (cache) |  |
| R33 | Stored-word arrays | P1:93-97; P2:91-95 | v9i | C | G1: "no theory bars the store itself: 2.6 names it"; D86 "user decision: reference convention" | 3 | 3 (imem, dmem, cache) | v2 README had REJECTED B8 Memory arrays: "P3164 p17-18 and SA-EDI count arrays" |
| R34 | Held addresses | P1:98 | v6 | F | P11.5 carrier (LAsset p2 / SAIF p2); from cache/debug_dtm FPs | none | - |  |
| R35 | Memory access address | P1:99 | v8 | T | v8 R4: IEEE P3164 white paper SRAM example; from the v7 failure analysis (imem addr) | none | 2 (units that are the store: imem, dmem) | v8 README: "R4 one memory" |
| R36-R37 | Operation selectors (a) (b) | P1:100-110; P2:68-74 | v5 | C | v5 U7 "U"; v11r drafter: "partly a reference convention" | 2 | 9 (coprocessors 7 + cpu_alu, cpu_lsu by name pattern; upper bound) |  |
| R38-R39 | Access command fields (a) (b) | P1:111-122; P2:36-39 | v6 | C | v6 CX1-ACF "user decision, reference convention"; v11r2 drafter "principle"; Phase 2 copy = v5 R1 "A" via ASSET_DEFINITION row 60 (a reference count: 0 of 118 transaction ports) | 2 | 25 (bus record ports) + register-access units | v2 README had REJECTED B2 Register access: "Contradicts step 2; the reference keeps such decisions in other units"; largest held-out recall loss (cpu_counters, cpu_regfile) |
| R40 | Per-region checks | P1:123 | v5 | C | v5 U9 "U" | 2 | 1 (cpu_pmp) |  |
| R41 | Arbitration bookkeeping | P1:124; P2:75 | v5 | C | v5 U10 "U"; v6 CX4.TF1 rewrite "U" | 2 | 1 (bus switch) |  |
| R42 | Requests waiting for a grant | P1:125; P2:76 | v8 | F | v8 R1: "the prompt's own definitions"; from the v7 failure analysis (bus a_req, b_req) | none | 1 (v8 README: "fits the one switch of the corpus") | keep rule |
| R43 | Processor context fields | P1:126 | v6 | C | v6 CX5.1 "user decision, reference convention" | 2 | 26 (modules with a ctrl_bus_t / ctrl_t record) |  |
| R44 | Control record ports | P1:127-131; P2:101-104 | v9g | C | N21 basis: 2.6 boundary clause + "Reference: every record port ... 11 of 11 record ports whole, 0 port fields"; PLAN_V9K: "needs a logged decision: the reference's whole-record convention" | none | 26 (non-bus record ports) | keep rule from held-out misses (D75); no logged decision found in the README or EXPERIMENT_LOG section 11 |
| R45 | Access command ports | P1:132-137; P2:105-109 | v9g | C | N22 basis: "the reference lists 10 of 10" + step 2 / 2.6 | none | - (non-record write/read enables and register addresses) | keep rule from held-out misses |
| R46 | Entry selects and register addresses | P1:138-143; P2:110-114 | v9g | C | N23 basis: 2.6 per-entry clause + "Reference: the three per-entry selects in the corpus"; PLAN_V9K: "needs a logged decision (N11's basis)" | none | 4 (counters, pwm, hwspinlock, regfile) | keep rule |
| R47 | Coprocessor progress state | P1:144-149; P2:116-120 | v9g | F | N25: step 2 and 2.6 "as written" + "Reference: the shifter's and the multiplier's progress state ... are listed" | none | 7 (cpu_cp_*) | keep rule; undoes Sequencing state for coprocessors |
| R48 | Done and wait inputs | P1:150-155; P2:127-131 | v9h | C | K11 basis: k1_shapes "holds for 4 reference entries and 0 non-reference ones" | none | 2 (cpu_control, xbus) | the criterion is the RTL fact that separates reference from non-reference elements |
| R49 | Link handshake ports | P1:156-161; P2:133-137 | v9h | C | K12 basis: "the 7 link handshake ports of the corpus ... are all reference entries and no non-reference port has the shape" | none | 3 (slink, uart, sdi) | same |
| R50 | Busy locks | P1:162-167; P2:139-143 | v9h | C | K13 basis: "holds for 2 reference entries (the debug module's and the debug transport's busy flags) and 0 non-reference" | none | 2 (debug_dm, debug_dtm) | same |
| R51 | Processor control-unit state | P1:168-172; P2:96-100 | v9i | C | G2: "only the reference's convention"; D86 "user decision: reference convention" | 3 | 1 (cpu_control) |  |
| R52 | Transfer records | P1:173-176; P2:82-85 | v9i | F | G7 "theory": 2.6 carrier (records whose fields the unit only copies); 4 of 5 FPs | none | 2-3 (cpu_frontend, cpu_icc; lower bound) |  |
| P2:34 | One primary per place (step 4 core sentence) | P2:34 | v9n_place | F | D94: "the prompt's own 2.6 / 2.7"; drafted from v9j FP analysis (78% of FPs internal registers under a right concept) | none | - | chosen on the held-out 26 (D92-D94) |
| R70 | Response status stages (one-bit re-timing register) | P2:115 | v6 | C | v6 CX10.1 "user decision, reference convention" | 2 | - | Phase 2 only |
| R73 | Boundary outputs | P2:122-126 | v9g | C | N24 basis: 2.6 + "the reference lists 74 of the 88 non-record output ports"; PLAN_V9K: "needs a logged decision (reads past 2.6's unmixed)" | none | - (non-record output ports) | Phase 2 only keep rule from held-out misses |
| R75 | Started flags | P2:132 | v5g | F | I7: copy of the Phase 1 step-3 clause (a flag recording that a count started is part of the count) | none | - | Phase 2 only |
| R77 | Constants-only gate wire into an instance | P2:138 | v6 | F | v6 LS2 (label rule): 2.6 decision clause | none | - | Phase 2 only |
| R79 | Step 5 Secondary | P2:145 | v1 | D | SAIF p2 primary / secondary split (2.7) | - | - |  |

## Counts (computed from the table above)

- rule blocks distinct: 49
- procedure or definition: 4
- content rules: 45
- C convention or reference count: 24
- F failure analysis with principle basis: 20
- T source cited for the rule: 1
- content rules written in v1: 0
- readme decision 1: 1
- readme decision 2: 17
- readme decision 3: 3
- readme none: 24
- convention rules not covered by readme: 7
- rules whose scope reaches at most 4 modules: 17
- rejected in v2 then admitted: 4
- content rules by origin version: v2 6, v3 1, v5 7, v5g 1, v6 11, v8 4, v9g 5, v9h 3, v9i 5, v9n_place 1, p1o_first 1
- convention-class rules not covered by any of the README's three decisions: Control record ports; Access command ports; Entry selects and register addresses; Done and wait inputs; Link handshake ports; Busy locks; Boundary outputs
- rules the v2 round rejected for lacking a basis or contradicting the prompt, later admitted: Sequencing state (v2 draft B3 Sequencers); Buffer and engine status bits (v2 draft B5 Buffer status); Stored-word arrays (v2 draft B8 Memory arrays); Access command fields (v2 draft B2 Register access) (prompts/two_phase_v2/README.md section 3)

## Code path (side audit, this session)

No code step between the model's reply and the scored 0.708 / 0.845 reads the reference list to add, remove, rename or relabel an element. The converter (chain.to_assets, chain.py:571-610) applies four reference-blind steps: primary label only, same-role expansion, one row per (entity, element), objective letter precedence; it keeps names outside the closed set (0 occurred). The checks (chain.py:222-328) report problems and never repair; the one-retry rule is format-only and fired 0 times. Verified now: 123 of 123 assets files equal to_assets(stored Phase 2 reply, stored Phase 1 concepts); all 123 phase records carry the current prompt shas (b4c962e16261 / 021cc963702d) and matching user-message shas; pooled 750 correct / 1060 listed reproduced (P 0.708), recall 750/888 = 0.845. The reference is read in four places, none of them a filter on the output: (1) the scorer itself (run_p1o_all41.py:46-60, exact name match, entity and objective not checked); (2) the recall denominator: compare_v8.refs (lines 51-52) keeps only reference names present in the closed set and eval_assets.load_refs caps repeats, so findable = 296 of 302 file entries, lifting recall from 0.828 (over 302) to 0.845 (over 296); precision unchanged; (3) module selection (labkit.gt_modules = modules with reference entries); (4) the prompt-leak guard (labkit.corpus_names, built from the reference and closed sets, used only by check_lab_prompt to forbid those names in prompts; chain._prepare refuses a version that fails it). The 'port-field convention' (labkit.collapse_port_fields) is not in the final number's path and, if applied, changes r2 listed 366 -> 364 only. The forbidden-name list DOES come from the reference (meta_tools.corpus_names reads data/ground_truth/manual_gt_neorv32.json, meta_tools.py:38-41), but it only prevents leakage; the port-field map does NOT (built from the closed set, build_kit_data.py:52). The prompt checker on two_phase_p1o_first is clean (no corpus identifier, no numeric hint) in both system prompts and both user templates.

Prompt checker output: checker self-test (3 planted problems caught): True / phase 1: 91,759 chars, sha12 b4c962e16261, clean / phase 1 user template: clean / phase 2: 98,852 chars, sha12 021cc963702d, clean / phase 2 user template: clean / EXIT=0

## Tuning against held-out by version (side audit; score_versions.py re-run, self-test PASS, identical to the stored score_versions.json)

| version | tuning P / R | held-out P / R | held-out used to choose it |
|---|---|---|---|
| v1 | 0.179 / 0.804 | 0.239 / 0.822 | False |
| v2 | 0.228 / 0.786 | 0.244 / 0.779 | False |
| v2a | 0.210 / 0.798 | not run (no held-out runs stored) / not run | False |
| v3 | 0.235 / 0.841 | not run / not run | False |
| v4 | 0.295 / 0.826 | not run / not run | False |
| v4a | 0.300 / 0.832 | 0.275 / 0.788 | False |
| v5 | 0.383 / 0.792 | 0.318 / 0.740 | False |
| v5f | 0.416 / 0.827 | not run / not run | False |
| v5g | 0.430 / 0.813 | not run / not run | False |
| v6 | 0.620 / 0.780 | 0.426 / 0.652 | False |
| v6d | 0.617 / 0.774 | not run / not run | False |
| v7 | 0.614 / 0.817 | 0.375 / 0.697 | False |
| v8 | 0.664 / 0.841 | 0.400 / 0.688 | False |
| v9 | 0.660 / 0.850 | 0.401 / 0.713 | True |
| v9f | 0.667 / 0.862 | 0.416 / 0.706 | True |
| v9g | 0.687 / 0.844 | 0.509 / 0.824 | True |
| v9h | 0.617 / 0.872 | 0.506 / 0.848 | True |
| v9i | 0.660 / 0.872 | 0.602 / 0.818 | True |
| v9j | 0.697 / 0.865 | 0.569 / 0.848 | True |
| v9n_place | not run / not run | 0.662 / 0.843 | True |
| p1o_first (FINAL) | 0.741 / 0.856 | 0.689 / 0.838 | True |

Denominators: tuning 109 findable entries per run (111 listed), held-out 187 (189), pooled over 3 runs unless the version has fewer runs (v9f, v9g, v9i tuning: 1 run; v9h: 2). Precision = correct / listed, exact name match.

Reference-blind baseline (blind_agent/REPORT.md, 2026-10-01, Claude executor, 2 runs): prompt D1 held-out P 0.362 / R 0.619; it "carries nothing tuned to these modules".
