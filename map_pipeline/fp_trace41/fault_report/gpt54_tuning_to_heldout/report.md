# Fault report: gpt54_tuning_to_heldout (tuning, final prompt, gpt-5.4)

How the generator's false positives (FP: listed, not in the reference) relate to its hits (TP: listed and in the reference), seen through the relationship types the map records for each element and the occurrence the generator cited for it. All numbers are computed by `assetgen_meta/fault_reporter.py`. This is the code-only report: no LLM was run, so R5 and the synthesis are absent.

Runs: assets_tuning18_m7e194es0opt1_g54_r0, assets_tuning18_m7e194es0opt1_g54_r1, assets_tuning18_m7e194es0opt1_g54_r2. Listed 672 (hits 273, FP 399), pooled over runs; 333 reference entries over these runs.

## Answer

- **Hits and FPs share their relationship types.** 21 of 21 relationship-class tokens occur on both. 16% of FPs have exactly the profile of some hit. In clusters of similar profiles (cut 0.35), 50% of FPs sit in clusters where hits are at least a fifth of the members (82% in clusters with any hit).
- **The profile predicts the reference's decision only weakly on a new module.** AUC for hit vs FP (0.5 = chance, 1 = perfect) from relationship classes: 0.776 in-sample, 0.644 leave one module out (logistic regression), 0.663 from the nearest profiles of other modules; with one row per element, 0.648 and 0.634. From exact record types: 0.827 in-sample, 0.675 leave one module out.
- **General rules cut FPs, but only at a cost and only part of them.** For 30 of 35 clusters with FPs (9 clusters hold hits only), a rule of the searched form drops some of the cluster's FPs and none of its hits; applied to every listed element, 9 of them drop hits elsewhere. All 30 together, on these elements (in-sample): 330 of 399 FPs and 97 of 273 hits dropped; P 0.406 -> 0.718, R 0.82 -> 0.529, F1 0.543 -> 0.609. On the heldout runs, never seen when the rules were found: 501 of 784 FPs and 158 of 497 hits dropped; P 0.388 -> 0.545, R 0.877 -> 0.598, F1 0.538 -> 0.57. For 5 clusters no rule of the searched form drops an FP without a hit; the largest of them by FP count are C12 (12 FP), C14 (9 FP), C19 (6 FP), C25 (3 FP), C26 (3 FP).

## R1. Relationship classes of hits and FPs

Share of hits and of FPs that have each token (pooled over runs).

| token | hits with it | share of hits | FPs with it | share of FPs |
|---|---|---|---|---|
| kind: signal | 154 | 56% | 337 | 84% |
| constant driver | 148 | 54% | 274 | 69% |
| storage: stored | 130 | 48% | 256 | 64% |
| reset | 129 | 47% | 237 | 59% |
| controlled <- internal | 107 | 39% | 225 | 56% |
| record field | 84 | 31% | 231 | 58% |
| controlled <- input port | 107 | 39% | 162 | 41% |
| control -> internal | 107 | 39% | 153 | 38% |
| data <- internal | 72 | 26% | 142 | 36% |
| data -> output port | 70 | 26% | 137 | 34% |
| storage: comb | 83 | 30% | 116 | 29% |
| data -> internal | 87 | 32% | 109 | 27% |
| data <- input port | 60 | 22% | 126 | 32% |
| kind: port-out | 63 | 23% | 37 | 9% |
| storage: not assigned here | 60 | 22% | 27 | 7% |
| updates itself (data) | 18 | 7% | 68 | 17% |
| kind: port-in | 56 | 20% | 25 | 6% |
| control -> output port | 31 | 11% | 41 | 10% |
| updates itself (control) | 22 | 8% | 20 | 5% |
| sub-unit port in | 21 | 8% | 15 | 4% |
| sub-unit port out | 7 | 3% | 1 | 0% |

## R2. Clusters of similar relationship profiles

| cut | clusters | FPs in clusters with any hit | share | FPs in clusters where hits are at least a fifth | share |
|---|---|---|---|---|---|
| 0.0 | 141 | 65 | 16% | 65 | 16% |
| 0.2 | 88 | 186 | 47% | 159 | 40% |
| 0.35 | 44 | 325 | 82% | 200 | 50% |
| 0.5 | 19 | 371 | 93% | 314 | 79% |

Exact record types instead of classes:

| cut | clusters | FPs in clusters with any hit | share |
|---|---|---|---|
| 0.0 | 171 | 45 | 11% |
| 0.2 | 119 | 143 | 36% |
| 0.35 | 65 | 255 | 64% |
| 0.5 | 30 | 353 | 88% |

Clusters at cut 0.35, most FPs first (listings pooled over runs):

| cluster | listings | hits | FPs | hit share | tokens in every member | hits in modules | FPs in modules | cited edges |
|---|---|---|---|---|---|---|---|---|
| C1 | 70 | 9 | 61 | 13% | constant driver; kind: signal; reset; storage: stored | bus, cpu_cp_muldiv, debug_dtm | cpu_cp_cfu, cpu_cp_muldiv, debug_dtm, spi, trng, twi, uart | {'CLOCKED_BY': 70} |
| C2 | 104 | 45 | 59 | 43% | kind: signal; storage: stored | cpu_cp_cfu, spi, trng, twi, uart, wdt | bus, cpu_cp_cfu, cpu_cp_muldiv, spi, twi, uart, wdt | {'CLOCKED_BY': 104} |
| C3 | 36 | 9 | 27 | 25% | constant driver; control -> internal; kind: signal; reset; storage: stored | bus, cpu_cp_muldiv, wdt | debug_dtm, spi, twi, uart, wdt | {'CLOCKED_BY': 36} |
| C4 | 27 | 0 | 27 | 0% | controlled <- input port; controlled <- internal; kind: signal; storage: stored |  | cache, imem | {'CLOCKED_BY': 23, 'DERIVES_FROM': 4} |
| C5 | 24 | 6 | 18 | 25% | constant driver; controlled <- internal; data -> output port; kind: signal; reset; storage: stored | hwspinlock, wdt | bus, trng, twi, uart, wdt | {'CLOCKED_BY': 24} |
| C6 | 21 | 3 | 18 | 14% | constant driver; controlled <- internal; kind: signal; record field; storage: comb | cpu_cp_muldiv | bus, cache | {'SELECTED_BY': 5, 'DERIVES_FROM': 6, 'GATED_BY': 10} |
| C7 | 20 | 3 | 17 | 15% | control -> internal; controlled <- input port; kind: signal; storage: comb | hwspinlock | bus, cpu_cp_muldiv, cpu_pmp | {'GATED_BY': 10, 'SELECTED_BY': 6, 'DERIVES_FROM': 4} |
| C8 | 18 | 3 | 15 | 17% | constant driver; controlled <- internal; kind: signal; reset; storage: stored | bus | cache, cpu_cp_muldiv, debug_dtm, spi | {'CLOCKED_BY': 16, 'GATED_BY': 1, 'SELECTED_BY': 1} |
| C9 | 16 | 2 | 14 | 12% | constant driver; kind: signal; record field; reset; storage: comb | cache | cache | {'none': 16} |
| C10 | 17 | 4 | 13 | 24% | control -> internal; kind: port-in; storage: not assigned here | cache, cpu_cp_cfu | cache, cpu_cp_cfu, sys | {'GATES': 16, 'SELECTS': 1} |
| C11 | 13 | 0 | 13 | 0% | controlled <- internal; data <- input port; kind: signal; record field; storage: comb |  | bus, cache | {'COPIES': 3, 'DERIVES_FROM': 7, 'SELECTED_BY': 3} |
| C12 | 36 | 24 | 12 | 67% | data <- internal; kind: port-out; storage: comb | spi, trng, twi, uart, wdt | spi, twi, wdt | {'COPIES': 27, 'DERIVES_FROM': 9} |
| C13 | 28 | 16 | 12 | 57% | constant driver; control -> internal; controlled <- internal; kind: signal; reset; storage: stored | bus, cpu_cp_muldiv, debug_dtm, wdt | bus, debug_dtm, spi, twi, wdt | {'CLOCKED_BY': 27, 'CONSTRAINED_BY': 1} |
| C14 | 52 | 43 | 9 | 83% | data -> internal; kind: port-in; storage: not assigned here | cache, cpu, cpu_cp_cfu, cpu_cp_muldiv, cpu_pmp, debug_dtm, spi, sys, twi, uart | cache, trng, twi | {'SOURCES': 34, 'CARRIES': 18} |
| C15 | 8 | 0 | 8 | 0% | controlled <- internal; kind: signal; record field; storage: comb; sub-unit port in |  | cache, trng | {'SELECTED_BY': 4, 'GATED_BY': 4} |

## R3. Can relationship types predict hit vs FP?

| profile | rows | in-sample AUC | leave-one-module-out AUC (logistic) | leave-one-module-out AUC (15 nearest, ties included) |
|---|---|---|---|---|
| relationship classes | all runs pooled (672) | 0.776 | 0.644 | 0.663 |
| relationship classes | one row per element (257) | 0.774 | 0.648 | 0.634 |
| exact record types | all runs pooled (672) | 0.827 | 0.675 | 0.626 |
| exact record types | one row per element (257) | 0.83 | 0.688 | 0.617 |

## R4. Rules found by code inside each cluster, tested on every listed element

The searched form: drop an element that has every token all members of the cluster share, plus up to two more tokens, unless it has one 'unless' token. A rule is clean when it drops some of the cluster's FPs and none of its hits; the table shows the clean rule dropping the most FPs (ties: fewest hits lost on all listed elements). It is then applied, as is, to every listed element and to the heldout runs (runs/assets_heldout26_m7e194es0opt1_g54_r0, runs/assets_heldout26_m7e194es0opt1_g54_r1, runs/assets_heldout26_m7e194es0opt1_g54_r2).

| cluster | tokens beyond the cluster's own | unless | FPs dropped in the cluster | all listed: FPs / hits dropped | all listed: P before -> after | heldout: FPs / hits dropped | heldout: P before -> after |
|---|---|---|---|---|---|---|---|
| C1 | data -> output port + record field | data -> internal | 30 of 61 | 72 / 24 | 0.406 -> 0.432 | 110 / 24 | 0.388 -> 0.412 |
| C2 | data <- input port + record field | data -> output port | 14 of 59 | 25 / 0 | 0.406 -> 0.422 | 41 / 6 | 0.388 -> 0.398 |
| C3 | controlled <- internal + data <- internal | data <- input port | 18 of 27 | 27 / 0 | 0.406 -> 0.423 | 88 / 0 | 0.388 -> 0.417 |
| C4 | (none) | - | 27 of 27 | 57 / 28 | 0.406 -> 0.417 | 99 / 18 | 0.388 -> 0.412 |
| C5 | (none) | controlled <- input port | 15 of 18 | 48 / 9 | 0.406 -> 0.429 | 42 / 9 | 0.388 -> 0.397 |
| C6 | (none) | data -> output port | 18 of 18 | 23 / 0 | 0.406 -> 0.421 | 31 / 0 | 0.388 -> 0.398 |
| C7 | (none) | data -> output port | 17 of 17 | 17 / 12 | 0.406 -> 0.406 | 26 / 11 | 0.388 -> 0.391 |
| C8 | data -> internal | - | 12 of 15 | 48 / 12 | 0.406 -> 0.426 | 165 / 12 | 0.388 -> 0.439 |
| C9 | data -> internal | - | 10 of 14 | 10 / 0 | 0.406 -> 0.412 | 2 / 0 | 0.388 -> 0.389 |
| C10 | control -> output port | - | 5 of 13 | 5 / 0 | 0.406 -> 0.409 | 0 / 6 | 0.388 -> 0.385 |
| C11 | (none) | - | 13 of 13 | 13 / 0 | 0.406 -> 0.414 | 8 / 0 | 0.388 -> 0.39 |
| C12 | no clean rule of the searched form | - | 0 of 12 | - | - | - | - |
| C13 | controlled <- input port | updates itself (control) | 4 of 12 | 13 / 6 | 0.406 -> 0.409 | 55 / 9 | 0.388 -> 0.401 |
| C14 | no clean rule of the searched form | - | 0 of 9 | - | - | - | - |
| C15 | (none) | - | 8 of 8 | 9 / 0 | 0.406 -> 0.412 | 9 / 0 | 0.388 -> 0.391 |

All 30 rules together on these elements (in-sample): 330 of 399 FPs and 97 of 273 hits dropped; P 0.406 -> 0.718, R 0.82 -> 0.529, F1 0.543 -> 0.609.

All 30 rules together on the heldout runs: 501 of 784 FPs and 158 of 497 hits dropped; P 0.388 -> 0.545, R 0.877 -> 0.598, F1 0.538 -> 0.57.
## R6. Fault ledger

`ledger.csv` lists every listed element with its cited occurrence, line, RTL text, edge, citation status, cluster and, for FPs, the cluster-level fault hypothesis. It traces each error to the evidence the generator used; the hypothesis is the LLM's, its citations are checked, its prose is not.

