# Why precision does not improve: final_gpt54_tuning (tuning, 3 runs)

Evidence comes from what the model reads and cites: the occurrence IDs and the relationship map of its input. Every count below is computed from the runs and the maps by `assetgen_meta/fp_diagnosis.py`; nothing is estimated. Precision (P) = share of listed elements that are in the reference; recall (R) = share of reference entries that were listed. TP = listed and in the reference; FP = listed and not in it.

Runs: assets_tuning18_m7e194es0opt1_g54_r0 P 0.418 R 0.784 (TP 87, FP 121); assets_tuning18_m7e194es0opt1_g54_r1 P 0.385 R 0.829 (TP 92, FP 147); assets_tuning18_m7e194es0opt1_g54_r2 P 0.418 R 0.847 (TP 94, FP 131). Mean P 0.407, R 0.820.

## Answer

- **Citations.** 96% of FP citations are verified (the cited occurrence is the element's own and the cited edge exists there and fits the role), against 99% for TPs. Verified is a necessary condition: it shows the model read the RTL as the map records it, not that the element is an asset.
- **Shared signatures.** 61% of FPs have a behaviour signature (L2) that at least one TP in these runs also has; with the exact set of record types (L3), 18%. A rule stated on the signature cannot drop those FPs without dropping the TPs that share it.
- **Signature-rate selectors over the whole map** (all 1,641 elements; list a signature when its reference rate on the other modules is high enough; best of L1-L3, threshold read off this set's curve, so optimistic): precision 0.17 (R 0.856) at recall >= 0.85 and 0.248 (R 0.793) at recall >= 0.70. With the rates fitted to this set itself (in-sample): 0.655 (R 0.856) at recall >= 0.85. The runs: P 0.407 at R 0.820. 2 of 111 reference entries have no element of that exact name in the map.
- **A filter on the model's own list** (keep an element when its signature's hit rate among the other modules' listed elements is high enough; best of L1-L3, threshold read off this set's curve): precision unreachable at recall >= 0.85 and 0.492 (R 0.73) at recall >= 0.70.
- **Whole concepts.** 237 FPs (59%) sit in 107 of 302 concepts (per run) that contain no reference element.
- **The precision edits** (D6), re-applied as code filters over 3 run(s): edit A would still drop 22 FPs and 0 TPs, edit B 30 FPs and 1 TPs, both (A then B) 52 FPs and 1 TPs.

Reading (each line follows from the numbers above):
- Precision 0.85 at recall >= 0.85 is not reached by any selector or filter of these forms with rates learnt on other modules (best leave-one-module-out 0.170; the in-sample values in D3 and D3b are fitted to the labels they score).
- Recall 0.85 is out of reach for any filter on this list: the runs' recall is 0.820.
- Hypothesis, not measured here: the FPs that share a signature with TPs (61% at L2) are decided by conventions of the reference that the RTL structure does not record. D4 shows pairs; the fault reporter tests this per relationship type.

## D1. Are false positives misreadings? (citation status)

| label | listed | verified | statuses |
|---|---|---|---|
| TP | 273 | 99% | {'verified': 271, 'map gap claimed': 2} |
| FP | 399 | 96% | {'verified': 385, 'map gap claimed': 14} |

## D2. Do false positives look like hits? (signature shared with a TP)

| level | signatures | FP in a signature that also holds a TP | share | FP in signatures with no TP |
|---|---|---|---|---|
| L1 | 9 | 398 of 399 | 100% | 1 |
| L2 | 56 | 242 of 399 | 61% | 157 |
| L3 | 150 | 73 of 399 | 18% | 326 |

Largest behaviour signatures (L2), pooled over runs:

| signature | FP | TP | TP in modules | FP in modules |
|---|---|---|---|---|
| signal field, stored; carries data into an output, written from an input, used here | 30 | 3 | uart | spi, uart |
| port-out, comb; no local use | 21 | 39 | cpu_cp_cfu, cpu_cp_muldiv, spi, sys, trng, twi | cache, cpu_cp_cfu, cpu_pmp, spi, twi, wdt |
| signal field, stored; carries data into an output, used here | 21 | 0 |  | cpu_cp_cfu, debug_dtm, spi, twi, uart |
| signal field, stored; updates itself, controls another element, used here | 19 | 12 | bus, cpu_cp_muldiv, debug_dtm | cpu_cp_cfu, debug_dtm, spi, twi, uart |
| signal field, comb; no local use | 18 | 0 |  | bus, cache |
| signal field, stored; controls another element, carries data into an output, written from an input, used here | 15 | 30 | spi, twi, uart, wdt | spi, twi, uart, wdt |
| signal field, comb; controls another element, used here | 15 | 14 | cache, cpu_cp_muldiv | cache, debug_dtm, twi |
| signal, comb; controls another element, used here | 14 | 3 | bus | bus, cpu_cp_muldiv, cpu_pmp |
| signal, stored; carries data into an output, written from an input, used here | 12 | 6 | cpu_cp_cfu, hwspinlock | cache |
| signal field, stored; updates itself, controls another element, carries data into an output, used here | 12 | 3 | wdt | cpu_cp_cfu, debug_dtm, twi |
| signal field, comb; written from an input | 12 | 0 |  | bus, cache |
| signal, stored; written from an input, used here | 12 | 0 |  | imem |

## D3. Signature-rate selectors over the whole map (model-independent)

All 1,641 elements of the tuning maps; 111 reference entries, 2 with no element of that exact name (recall by exact name can reach at most 0.982; the scorer also credits a record against one of its fields). A selector lists every element whose signature's reference rate is above a threshold. In-sample rates are fitted to the reference itself; leave-one-module-out rates come from the other modules only. In both, the best point at each recall is read off the curve of this set, so the values are optimistic. These are selectors of one form (signature rates); they do not bound a method that uses other information.

| level | signatures | in-sample P@R>=0.5 | P@R>=0.7 | P@R>=0.85 | leave-one-out P@R>=0.5 | P@R>=0.7 | P@R>=0.85 |
|---|---|---|---|---|---|---|---|
| L1 | 14 | 0.238 (R 0.514, 239 listed) | 0.211 (R 0.748, 393 listed) | 0.198 (R 0.892, 499 listed) | 0.192 (R 0.838, 484 listed) | 0.192 (R 0.838, 484 listed) | 0.17 (R 0.856, 559 listed) |
| L2 | 95 | 0.431 (R 0.595, 153 listed) | 0.382 (R 0.703, 204 listed) | 0.332 (R 0.856, 286 listed) | 0.248 (R 0.793, 355 listed) | 0.248 (R 0.793, 355 listed) | 0.066 (R 0.982, 1641 listed) |
| L3 | 275 | 0.925 (R 0.559, 67 listed) | 0.81 (R 0.73, 100 listed) | 0.655 (R 0.856, 145 listed) | 0.245 (R 0.721, 326 listed) | 0.245 (R 0.721, 326 listed) | 0.066 (R 0.982, 1641 listed) |

For comparison, the runs above: P 0.407 at R 0.820.

### D3b. A code filter on the model's own list

Each listed element gets its signature's hit rate among the listed elements; the filter keeps elements above a threshold. Leave-one-module-out rates come from the other modules' rows only. Recall counts the reference entries of all pooled runs (333).

| level | in-sample P@R>=0.7 | P@R>=0.85 | leave-one-out P@R>=0.7 | P@R>=0.85 |
|---|---|---|---|---|
| L1 | 0.433 (R 0.76, 584 listed) | - | 0.407 (R 0.82, 671 listed) | - |
| L2 | 0.64 (R 0.733, 381 listed) | - | 0.492 (R 0.73, 494 listed) | - |
| L3 | 0.902 (R 0.721, 266 listed) | - | 0.406 (R 0.82, 672 listed) | - |

Reference listing rate of the largest L2 signatures (all map elements):

| signature | elements | in the reference | rate |
|---|---|---|---|
| port-in, not assigned here; used here | 58 | 15 | 0.259 |
| port-out, comb; no local use | 64 | 13 | 0.203 |
| signal field, stored; controls another element, carries data into an output, written from an input, used here | 15 | 10 | 0.667 |
| port-out, stored; no local use | 11 | 8 | 0.727 |
| port-in, not assigned here; controls another element, used here | 15 | 6 | 0.4 |
| signal field, comb; controls another element, used here | 22 | 5 | 0.227 |
| signal field, stored; updates itself, controls another element, used here | 18 | 4 | 0.222 |
| signal, not assigned here; feeds a sub-unit, fed by a sub-unit, used here | 11 | 4 | 0.364 |
| signal, stored; updates itself, controls another element, used here | 9 | 4 | 0.444 |
| port-in, not assigned here; no local use | 19 | 3 | 0.158 |
| signal, stored; controls another element, used here | 13 | 3 | 0.231 |
| signal, stored; carries data into an output, used here | 3 | 3 | 1.0 |
| signal, comb; controls another element, used here | 14 | 2 | 0.143 |
| port-in, not assigned here; feeds a sub-unit, used here | 10 | 2 | 0.2 |

## D4. Minimal pairs: same map evidence, opposite reference decision

**port-in, not assigned here; controls another element, used here, GATES** (L3; 9 FP, 4 TP in these runs)

| | module | element | role | occurrence -> line | cited edge | RTL line | status |
|---|---|---|---|---|---|---|---|
| TP | cpu_cp_cfu | `start_i` | sets | 2 -> 204 | GATES xtea.done | `if (start_i = '1') and (rtype_i = r3type_c) then` | verified |
| FP | cache | `clr_i` | sets | 2 -> 380 | GATES valid_mem | `if (clr_i = '1') then` | verified |

Record types: TP GATES; FP GATES.

**port-out, comb; COPIES** (L3; 9 FP, 18 TP in these runs)

| | module | element | role | occurrence -> line | cited edge | RTL line | status |
|---|---|---|---|---|---|---|---|
| TP | trng | `data_o` | exit port | 2 -> 366 | COPIES sample_sreg | `data_o  <= sample_sreg;` | verified |
| FP | spi | `spi_clk_o` | exit port | 2 -> 344 | COPIES rtx_engine.sck | `spi_clk_o <= rtx_engine.sck;` | verified |

Record types: TP COPIES; FP COPIES.

**signal field, stored; controls another element, carries data into an output, written from an input, used here, is gated, is reset, CARRIES, CLOCKED_BY, DERIVES_FROM, GATED_BY, GATES, RESET_BY** (L3; 9 FP, 3 TP in these runs)

| | module | element | role | occurrence -> line | cited edge | RTL line | status |
|---|---|---|---|---|---|---|---|
| TP | wdt | `ctrl.enable` | stores | 3 -> 94 | CLOCKED_BY clk_i | `ctrl.enable  <= bus_req_i.data(ctrl_enable_c);` | verified |
| FP | spi | `ctrl.highspeed` | stores | 3 -> 145 | CLOCKED_BY clk_i | `ctrl.highspeed    <= bus_req_i.data(ctrl_highspeed_c);` | verified |

Record types: TP CARRIES, CLOCKED_BY, DERIVES_FROM, GATED_BY, GATES, RESET_BY; FP CARRIES, CLOCKED_BY, DERIVES_FROM, GATED_BY, GATES, RESET_BY.

**signal field, comb; controls another element, used here, is gated, GATED_BY, GATES** (L3; 7 FP, 6 TP in these runs)

| | module | element | role | occurrence -> line | cited edge | RTL line | status |
|---|---|---|---|---|---|---|---|
| TP | cpu_cp_muldiv | `div.start` | computes | 2 -> 155 | GATED_BY valid_cmd | `div.start <= '1' when (valid_cmd = '1') and (ctrl_i.ir_funct3(2) = '1') else '0';` | verified |
| FP | debug_dtm | `dr_trigger.valid` | computes | 2 -> 161 | GATED_BY dr_trigger.sreg | `dr_trigger.valid <= '1' when (dr_trigger.sreg = "01") else '0';` | verified |

Record types: TP GATED_BY, GATES; FP GATED_BY, GATES.

**port-in, not assigned here; used here, carries data inward, SOURCES** (L3; 6 FP, 24 TP in these runs)

| | module | element | role | occurrence -> line | cited edge | RTL line | status |
|---|---|---|---|---|---|---|---|
| TP | cpu | `mei_i` | sets | 2 -> 276 | SOURCES irq_machine | `irq_machine <= mti_i & mei_i & msi_i;` | verified |
| FP | cache | `wdata_i` | sets | 2 -> 414 | SOURCES data_mem_b0 | `data_mem_b0(to_integer(unsigned(acc_adr))) <= wdata_i(7 downto 0);` | verified |

Record types: TP SOURCES; FP SOURCES.

**signal, stored; updates itself, controls another element, used here, is gated, is reset, CLOCKED_BY, GATED_BY, GATES, RESET_BY, SELECTED_BY, SELECTS** (L3; 3 FP, 3 TP in these runs)

| | module | element | role | occurrence -> line | cited edge | RTL line | status |
|---|---|---|---|---|---|---|---|
| TP | bus | `state` | stores | 7 -> 927 | CLOCKED_BY clk_i | `state <= "10";` | verified |
| FP | debug_dtm | `tap_ctrl_state` | stores | 4 -> 123 | CLOCKED_BY clk_i | `when LOGIC_RESET => if (tap_sync.tms = '0') then tap_ctrl_state <= RUN_IDLE;   else tap_ct` | verified |

Record types: TP CLOCKED_BY, GATED_BY, GATES, RESET_BY, SELECTED_BY, SELECTS; FP CLOCKED_BY, GATED_BY, GATES, RESET_BY, SELECTED_BY, SELECTS.

## D5. Whole concepts the reference does not have

107 of 302 concepts (pooled over runs) contain no TP. They hold 237 FPs, 59% of all. The rest are extra elements inside concepts the reference does have.

## D6. Did the model follow the precision edits? (entries each edit would still remove)

| run | P | R | edit A removes FP / TP | edit B removes FP / TP |
|---|---|---|---|---|
| assets_tuning18_m7e194es0opt1_g54_r0 | 0.418 | 0.784 | 8 / 0 | 6 / 0 |
| assets_tuning18_m7e194es0opt1_g54_r1 | 0.385 | 0.829 | 8 / 0 | 11 / 1 |
| assets_tuning18_m7e194es0opt1_g54_r2 | 0.418 | 0.847 | 6 / 0 | 13 / 0 |

Edit A: a stored internal signal, whatever role it was given, is listed only when its records show a use (it controls another element, carries data into an output, or feeds a sub-unit), or it is a setting written from an input that a computation here reads. Edit B, as shipped: a register whose value-taking records name one other listed element and nothing else, not even itself, is a one-clock copy, unless that element is combinational and copies it or drives only it. For a run of a prompt without these edits the numbers show what they would remove; for a run with them, the FPs are entries the model kept against the edit.

## D7. Which families moved between versions (mean per run, FP / TP)

| family | final prompt, gpt-5.4 (3 runs) |
|---|---|
| internal state register | 36.3 / 14.3 |
| setting written from an input | 33.3 / 18.0 |
| combinational decision | 13.7 / 8.3 |
| combinational data | 13.0 / 2.3 |
| output port | 12.3 / 21.0 |
| data register | 10.7 / 3.0 |
| input port | 8.3 / 18.7 |
| sub-unit interface signal | 5.3 / 5.3 |

Read across a row: a family whose FPs fall while its TPs stay is one an edit moved.

