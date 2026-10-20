# Fault report: claude_tuning_to_heldout (tuning, final prompt, Claude)

How the generator's false positives (FP: listed, not in the reference) relate to its hits (TP: listed and in the reference), seen through the relationship types the map records for each element and the occurrence the generator cited for it. All numbers are computed by `assetgen_meta/fault_reporter.py`. This is the code-only report: no LLM was run, so R5 and the synthesis are absent.

Runs: assets_opt_v1_r0, assets_opt_v1_r1, assets_opt_v1_r2. Listed 838 (hits 311, FP 527), pooled over runs; 333 reference entries over these runs.

## Answer

- **Hits and FPs share their relationship types.** 21 of 21 relationship-class tokens occur on both. 26% of FPs have exactly the profile of some hit. In clusters of similar profiles (cut 0.35), 45% of FPs sit in clusters where hits are at least a fifth of the members (79% in clusters with any hit).
- **The profile predicts the reference's decision only weakly on a new module.** AUC for hit vs FP (0.5 = chance, 1 = perfect) from relationship classes: 0.762 in-sample, 0.629 leave one module out (logistic regression), 0.637 from the nearest profiles of other modules; with one row per element, 0.62 and 0.594. From exact record types: 0.808 in-sample, 0.661 leave one module out.
- **General rules cut FPs, but only at a cost and only part of them.** For 31 of 39 clusters with FPs (8 clusters hold hits only), a rule of the searched form drops some of the cluster's FPs and none of its hits; applied to every listed element, 11 of them drop hits elsewhere. All 31 together, on these elements (in-sample): 374 of 527 FPs and 114 of 311 hits dropped; P 0.371 -> 0.563, R 0.934 -> 0.592, F1 0.531 -> 0.577. On the heldout runs, never seen when the rules were found: 227 of 359 FPs and 55 of 176 hits dropped; P 0.329 -> 0.478, R 0.931 -> 0.64, F1 0.486 -> 0.548. For 8 clusters no rule of the searched form drops an FP without a hit; the largest of them by FP count are C8 (18 FP), C9 (18 FP), C13 (15 FP), C15 (12 FP), C30 (4 FP), C31 (4 FP).

## R1. Relationship classes of hits and FPs

Share of hits and of FPs that have each token (pooled over runs).

| token | hits with it | share of hits | FPs with it | share of FPs |
|---|---|---|---|---|
| kind: signal | 176 | 57% | 444 | 84% |
| constant driver | 152 | 49% | 328 | 62% |
| reset | 132 | 42% | 292 | 55% |
| storage: stored | 132 | 42% | 286 | 54% |
| record field | 86 | 28% | 296 | 56% |
| controlled <- internal | 113 | 36% | 256 | 49% |
| control -> internal | 122 | 39% | 240 | 46% |
| controlled <- input port | 110 | 35% | 153 | 29% |
| storage: comb | 83 | 27% | 168 | 32% |
| data -> output port | 70 | 22% | 161 | 31% |
| data -> internal | 99 | 32% | 123 | 23% |
| data <- internal | 71 | 23% | 143 | 27% |
| storage: not assigned here | 96 | 31% | 73 | 14% |
| data <- input port | 58 | 19% | 102 | 19% |
| kind: port-in | 72 | 23% | 40 | 8% |
| updates itself (data) | 18 | 6% | 89 | 17% |
| kind: port-out | 63 | 20% | 43 | 8% |
| control -> output port | 36 | 12% | 67 | 13% |
| sub-unit port in | 31 | 10% | 67 | 13% |
| sub-unit port out | 27 | 9% | 43 | 8% |
| updates itself (control) | 24 | 8% | 36 | 7% |

## R2. Clusters of similar relationship profiles

| cut | clusters | FPs in clusters with any hit | share | FPs in clusters where hits are at least a fifth | share |
|---|---|---|---|---|---|
| 0.0 | 147 | 139 | 26% | 121 | 23% |
| 0.2 | 89 | 266 | 50% | 230 | 44% |
| 0.35 | 47 | 417 | 79% | 236 | 45% |
| 0.5 | 18 | 527 | 100% | 432 | 82% |

Exact record types instead of classes:

| cut | clusters | FPs in clusters with any hit | share |
|---|---|---|---|
| 0.0 | 180 | 100 | 19% |
| 0.2 | 120 | 224 | 42% |
| 0.35 | 65 | 395 | 75% |
| 0.5 | 30 | 502 | 95% |

Clusters at cut 0.35, most FPs first (listings pooled over runs):

| cluster | listings | hits | FPs | hit share | tokens in every member | hits in modules | FPs in modules | cited edges |
|---|---|---|---|---|---|---|---|---|
| C1 | 99 | 42 | 57 | 42% | data <- input port; kind: signal; storage: stored | cpu_cp_cfu, spi, trng, twi, uart, wdt | bus, cpu_cp_muldiv, spi, twi, uart, wdt | {'CLOCKED_BY': 99} |
| C2 | 61 | 9 | 52 | 15% | constant driver; control -> internal; controlled <- internal; kind: signal; reset; storage: stored | bus, cpu_cp_muldiv, wdt | cpu_cp_cfu, cpu_pmp, debug_dtm, spi, twi, uart, wdt | {'CLOCKED_BY': 61} |
| C3 | 57 | 9 | 48 | 16% | constant driver; data <- internal; kind: signal; reset; storage: stored | bus, cpu_cp_muldiv, debug_dtm | cpu_cp_cfu, debug_dtm, spi, trng, twi, uart | {'CLOCKED_BY': 52, 'DERIVES_FROM': 5} |
| C4 | 34 | 3 | 31 | 9% | constant driver; kind: signal; record field; reset; storage: comb | cache | bus, cache | {'none': 34} |
| C5 | 30 | 0 | 30 | 0% | controlled <- internal; kind: signal; record field; storage: comb; sub-unit port in |  | cache, spi, trng, twi, uart | {'SELECTED_BY': 6, 'GATED_BY': 24} |
| C6 | 45 | 21 | 24 | 47% | constant driver; control -> internal; kind: signal; reset; storage: stored | bus, cpu_cp_muldiv, debug_dtm, wdt | bus, debug_dtm, spi, trng, twi, wdt | {'CLOCKED_BY': 45} |
| C7 | 36 | 12 | 24 | 33% | control -> internal; kind: port-in; storage: not assigned here | cache, cpu_cp_cfu | cache, cpu_cp_cfu, sys, wdt | {'GATES': 33, 'SELECTS': 3} |
| C8 | 42 | 24 | 18 | 57% | data <- internal; kind: port-out; storage: comb | spi, trng, twi, uart, wdt | spi, trng, twi, wdt | {'COPIES': 27, 'DERIVES_FROM': 15} |
| C9 | 21 | 3 | 18 | 14% | controlled <- input port; kind: signal; record field; storage: comb; sub-unit port in | trng | spi, twi, uart | {'GATED_BY': 21} |
| C10 | 21 | 3 | 18 | 14% | constant driver; controlled <- internal; kind: signal; reset; storage: stored | bus | cpu_cp_muldiv, debug_dtm, spi, sys, twi, uart | {'CLOCKED_BY': 9, 'GATED_BY': 12} |
| C11 | 16 | 0 | 16 | 0% | controlled <- input port; controlled <- internal; data <- input port; kind: signal; storage: stored |  | cache, imem | {'CLOCKED_BY': 16} |
| C12 | 16 | 0 | 16 | 0% | constant driver; controlled <- internal; kind: signal; reset; storage: stored |  | trng, twi, uart, wdt | {'CLOCKED_BY': 16} |
| C13 | 27 | 12 | 15 | 44% | kind: signal; storage: not assigned here; sub-unit port in; sub-unit port out | cpu | cpu | {'CONNECTS': 27} |
| C14 | 16 | 2 | 14 | 12% | control -> internal; controlled <- input port; kind: signal; storage: comb | hwspinlock | bus, cpu_cp_muldiv, cpu_pmp | {'GATED_BY': 16} |
| C15 | 63 | 51 | 12 | 81% | data -> internal; kind: port-in; storage: not assigned here | cache, cpu, cpu_cp_cfu, cpu_cp_muldiv, cpu_pmp, debug_dtm, spi, sys, twi, uart | cache, trng, twi | {'SOURCES': 39, 'CARRIES': 21, 'GATES': 3} |

## R3. Can relationship types predict hit vs FP?

| profile | rows | in-sample AUC | leave-one-module-out AUC (logistic) | leave-one-module-out AUC (15 nearest, ties included) |
|---|---|---|---|---|
| relationship classes | all runs pooled (838) | 0.762 | 0.629 | 0.637 |
| relationship classes | one row per element (295) | 0.756 | 0.62 | 0.594 |
| exact record types | all runs pooled (838) | 0.808 | 0.661 | 0.631 |
| exact record types | one row per element (295) | 0.8 | 0.66 | 0.61 |

## R4. Rules found by code inside each cluster, tested on every listed element

The searched form: drop an element that has every token all members of the cluster share, plus up to two more tokens, unless it has one 'unless' token. A rule is clean when it drops some of the cluster's FPs and none of its hits; the table shows the clean rule dropping the most FPs (ties: fewest hits lost on all listed elements). It is then applied, as is, to every listed element and to the heldout runs (runs/assets_opt_heldout_v1_r0).

| cluster | tokens beyond the cluster's own | unless | FPs dropped in the cluster | all listed: FPs / hits dropped | all listed: P before -> after | heldout: FPs / hits dropped | heldout: P before -> after |
|---|---|---|---|---|---|---|---|
| C1 | record field | data -> output port | 12 of 57 | 21 / 0 | 0.371 -> 0.381 | 19 / 1 | 0.329 -> 0.34 |
| C2 | data <- internal | data <- input port | 33 of 52 | 39 / 0 | 0.371 -> 0.389 | 34 / 0 | 0.329 -> 0.351 |
| C3 | data -> output port + record field | data -> internal | 28 of 48 | 28 / 0 | 0.371 -> 0.384 | 4 / 0 | 0.329 -> 0.331 |
| C4 | data -> internal | - | 22 of 31 | 22 / 0 | 0.371 -> 0.381 | 3 / 0 | 0.329 -> 0.331 |
| C5 | (none) | - | 30 of 30 | 30 / 0 | 0.371 -> 0.385 | 12 / 0 | 0.329 -> 0.337 |
| C6 | controlled <- input port + controlled <- internal | updates itself (control) | 9 of 24 | 18 / 6 | 0.371 -> 0.375 | 32 / 3 | 0.329 -> 0.346 |
| C7 | data -> output port | - | 6 of 24 | 6 / 0 | 0.371 -> 0.374 | 0 / 2 | 0.329 -> 0.326 |
| C8 | no clean rule of the searched form | - | 0 of 18 | - | - | - | - |
| C9 | no clean rule of the searched form | - | 0 of 18 | - | - | - | - |
| C10 | data -> internal | - | 15 of 18 | 44 / 12 | 0.371 -> 0.382 | 53 / 3 | 0.329 -> 0.361 |
| C11 | (none) | - | 16 of 16 | 25 / 9 | 0.371 -> 0.376 | 15 / 5 | 0.329 -> 0.332 |
| C12 | (none) | - | 16 of 16 | 167 / 57 | 0.371 -> 0.414 | 146 / 12 | 0.329 -> 0.435 |
| C13 | no clean rule of the searched form | - | 0 of 15 | - | - | - | - |
| C14 | (none) | data -> output port | 14 of 14 | 14 / 12 | 0.371 -> 0.368 | 11 / 3 | 0.329 -> 0.332 |
| C15 | no clean rule of the searched form | - | 0 of 12 | - | - | - | - |

All 31 rules together on these elements (in-sample): 374 of 527 FPs and 114 of 311 hits dropped; P 0.371 -> 0.563, R 0.934 -> 0.592, F1 0.531 -> 0.577.

All 31 rules together on the heldout runs: 227 of 359 FPs and 55 of 176 hits dropped; P 0.329 -> 0.478, R 0.931 -> 0.64, F1 0.486 -> 0.548.
## R6. Fault ledger

`ledger.csv` lists every listed element with its cited occurrence, line, RTL text, edge, citation status, cluster and, for FPs, the cluster-level fault hypothesis. It traces each error to the evidence the generator used; the hypothesis is the LLM's, its citations are checked, its prose is not.

