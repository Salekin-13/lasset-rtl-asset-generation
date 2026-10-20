# two_phase_v9: v8 + a narrower Forwarded transactions rule (built 2026-10-14; NOT run)

**Status:** built, reviewed and checked; not run. Nothing below is a measurement of v9 on the model.

**Wording:** proposed by Claude in the held-out analysis and revised after a review (below); the user asked to apply
the narrowing to v8, agreed to build it as v9, and asked for the check and the fix ("do the check & the fix if needed").

## What changed (two additions to v8, nothing else)

Built by analysis/prompt_builds/v9/make_v9.py. common.md, both user templates and both OUTPUT sections are
byte-identical to v8.

- **phase1.md line 27 (Forwarded transactions), end of the first sentence:** "...is not a conceptual asset of this
  unit; this rule, its sentences on relayed data included, never covers a bus whose address this unit drives on a
  non-record output port of its own and whose acknowledge it takes on a non-record input port of its own (judge from
  port names which ports are that bus's address, acknowledge and other lines, and say so): the request it drives onto
  that bus's ports and the response it takes from them are judged as usual, as information leaving and entering the
  unit there."
- **phase2.md line 34, after the relayed-data block ("... which a computed result, and say so."):** "The relayed-data
  sentences above never bar a port of a bus whose address this unit drives on a non-record output port of its own and
  whose acknowledge it takes on a non-record input port of its own (judge from port names which ports are that bus's
  address, acknowledge and other lines, and say so): judge each such port as usual (2.6, 2.7); under a conceptual asset
  about what crosses that bus, the relayed-data bar still keeps every other element from being primary, but each can be
  a secondary of those ports (2.7)."

Words: phase1.md 6,979 -> 7,061 (+82); phase2.md 8,461 -> 8,553 (+92). System prompt sha12: phase 1 `a91834bb2082`,
phase 2 `0d77634a9d2b` (v8: `88a651707c04` / `b61510131dbf`).

## Why (measured; analysis/heldout_versions__gpt-5.6-luna__high__r0-r2/)

- The held-out recall drop at v1 -> v2 is one module: xbus, correct finds 27 -> 9 over r0-r2. The other 25 held-out
  modules lose 6, the same as the 15 tuning modules (sign test over modules p = 1.00).
- In every v2 run Phase 1 put xbus's outgoing request under Not Kept and cited the rule, so its separate external-bus
  ports were never named; Phase 2 and common.md were byte-identical between v1 and v2.
- The rule's own condition ("without storing, computing or deciding it") is shaky for xbus: it computes its cycle line
  from the strobe and its own pending state (rtl.txt line 146), gates the returned data with pending (154), and computes
  the acknowledge and error with its own timeout (155-156).
- Everything the rule removed on the tuning modules at v1 -> v2 is a record port or a record field (bus switch, cache).
- v8 finds xbus_adr_o and xbus_we_o in 3 of 3 runs (v6's "a transfer's address and direction" clause) but xbus_dat_o,
  xbus_dat_i, xbus_stb_o in 0 of 3 and xbus_cyc_o, xbus_ack_i, xbus_err_i in 1 of 3.

## Review (Claude agents, 2026-10-14; analysis/two_phase_v9__gpt-5.6-luna__high__r0-r2/review/)

The review pack (make_review_pack.py; leak check PASS: no reference list, no scores) holds the rule, the 61 v8 Phase 1
Not Kept rows in all 41 modules that cite forwarding or relayed data, and every module's ports.

- **Round 1, first wording** ("a bus whose signals are separate non-record ports ... (an address, data, strobe or
  acknowledge line each on a port of its own)"): two blind judges, a scope skeptic and a conflict skeptic. The wording
  named no direction, so it also reached a register-access port the unit answers (cpu_icc: both judges, 3 rows) and was
  ambiguous for an operand port (cpu_alu), a read-data input (cpu_control), a CPU-side access port (cpu_lsu) and a
  test-access port (debug_dtm). Phase 2's "this sentence" pointed at itself; Phase 1 freed the information while Phase 2
  freed only the port; the Phase 2 sentence split the bar from its "Judged as usual" list and named a rule Phase 2
  cannot see.
- **Fix:** the bus is one whose address the unit drives on a non-record output port of its own and whose acknowledge it
  takes on a non-record input port of its own. Measured by port name over every entity of the 41 modules: only xbus
  (xbus_adr_o, xbus_ack_i) has both; it is also the only entity with either.
- **Round 2, revised wording:** a blind judge found the clause changes 7 of the 61 rows, all in xbus (5 fully, 2
  partly), and no other module's; scope sweep: slink's transmit side (a destination output, a ready input) a remote
  "maybe", with no row there. A conflict skeptic confirmed the other fixes and found one medium point (the kept bar's
  premise "Phase 1 does not keep such a concept, so it has no secondary" became false for this bus) and two low ones;
  applied as worded: the bar "still keeps every other element from being primary, but each can be a secondary of those
  ports (2.7)"; "judge from port names which ports are that bus's address, acknowledge and other lines"; "judge each
  such port as usual (2.6, 2.7)". These last edits were checked in code, not by a third agent round.

## Expected effect (reasoning, not measured)

- Gain on xbus: the six ports above (up to +14 correct runs). v1, without the rule, found all of them in every run.
- Likely cost on xbus: xbus_sel_o and xbus_tag_o (not in the reference) come back as false positives (up to +6 runs;
  v1 listed each in 3 of 3 runs). Internal signals (bus_req.*, bus_rsp.*) stay barred from primary.
- No change elsewhere: no other entity in the corpus meets the clause's condition.

## What it breaks

- A new version: compare v9 with v8 only on the same modules and runs.
- The basis is partly a reference observation (xbus lists its external-bus ports). xbus is in tuning_v2, so using it is
  tuning, not a held-out leak. cpu_lsu (heldout_v2) was not used to change a rule.

## Readings, set before the run (analysis/two_phase_v9__gpt-5.6-luna__high__r0-r2/compare_v9.py)

v8 baseline, pooled r0-r2 (TP / FP runs): xbus 12 / 19, bus 32 / 17, cache 5 / 16, cpu 35 / 23, debug_dtm 13 / 20,
cpu_icc 4 / 10, cpu_control 16 / 175.

1. **Targets:** xbus_dat_o, xbus_dat_i, xbus_stb_o (v8: 0 of 3 runs each). Supports the narrowing if 2+ of them are
   found in 2+ v9 runs; FALSIFIED if none is. (xbus_cyc_o, xbus_ack_i, xbus_err_i, v8 1 each, are reported.)
2. **No lost find:** xbus_adr_o and xbus_we_o stay found in 2+ v9 runs each.
3. **No tuning cost:** bus + cache + cpu pooled: FALSIFIED if TP <= 66 (v8 72) or FP >= 62 (v8 56). A change of 6 is
   two runs' worth of v8's per-run spread; a chosen cut.
4. **No leak on xbus:** xbus FP runs <= 25 (v8 19, plus at most 6 for xbus_sel_o and xbus_tag_o); new FP names listed.
5. **Mechanism (reported):** per run, whether an xbus Phase 1 concept anchors xbus_dat_o, xbus_stb_o or xbus_dat_i, and
   which separate xbus ports forwarding/relayed Not Kept rows still name (v8: xbus_dat_i in r0; xbus_cyc_o, xbus_stb_o
   in r1).
6. **No reach into CSR read-data ports:** FP runs of cpu_icc csr_rdata_o, cpu_control xcsr_rdata_i and cpu_control
   csr_rdata_o, summed (v8 3): FALSIFIED if v9 >= 5.
7. **No reach into debug_dtm:** FALSIFIED if TP <= 10 (v8 13) or FP >= 23 (v8 20); tap_reg.bypass FP runs reported.

Watch in the later full runs (not in this job): slink's transmit side; a Phase 1 reply for any unit other than xbus
saying it found such a bus would show the clause reaching too far.

## How to run (paid; the user sends it)

- Notebook final/pio/pio_pilot.ipynb, cell 9 is set up: `JOBS = [("two_phase_v9", r) for r in (0, 1, 2)]`, `ALL = ` the
  seven modules above, `RUN_MANY = False` (preview only: 42 calls). Run it once to see the preview, then set
  `RUN_MANY = True` and run it again. No kernel restart is needed: the cell reloads chain, labkit and the checker.
- Cost: about USD 1.25 (v8's 3 runs on these seven modules cost USD 1.21 by stored usage; v9's prompts are about 1%
  longer).
- Afterwards: `python final/pio/lab/analysis/two_phase_v9__gpt-5.6-luna__high__r0-r2/compare_v9.py`.
- If the readings hold: a full v9 run on tuning_v2 (about USD 4.0 by v8's stored usage) and heldout_v2 (about USD 1.8)
  before v9 replaces v8.

## Checks passed (make_v9.py --write, final wording)

- The project prompt checker (corpus identifiers, numeric hints, comments, the final-JSON phrase, both user templates):
  clean; its planted self-test caught all 3 problems.
- chain.new_format for both phases; OUTPUT sections byte-identical to v8; all 35 sentences (6+ words) shared by the two
  v8 phase bodies still in both; both new texts present; common.md, user templates and line ends as v8.
- A sentence-level diff against v8 shows only the two additions.
