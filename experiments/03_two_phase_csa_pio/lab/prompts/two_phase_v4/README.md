# two_phase_v4 — v3 + bus record ports are never primary (2026-10-12, not run)

Base: `two_phase_v3`. **One change, in common.md section 2.6** (change C10 of
`analysis/two_phase_v2__gpt-5.6-luna__high__r0-r2/V3_PHASE1_PROPOSAL.md`): a new line after the line that makes forwarding
wires and read-back words candidate secondaries (v2/v3 common.md line 99):

> A bus request record port (one that carries an address, data and a strobe) or bus response record port (one that carries
> data, an acknowledge and an error flag), or any field of one, is not a primary. Label primary the element inside the unit
> that the access sets, decides or returns.

phase1.md, phase2.md and both user templates are byte-identical to v3 (`analysis/prompt_builds/make_v4.py` asserts it).
System prompts (check_lab_prompt, clean): Phase 1 36,437 chars, sha12 `82e24b9513ae`; Phase 2 39,837 chars, sha12
`ca98760b47a5`. `build_check.py two_phase_v4 --common-changed --phase1-changed`: PASS.

## Why, and its basis

- Measured on the stored v2 runs (`p1_rules/c10_busfields.py`, self-test passed): bus request/response record ports and their
  fields are 176 / 71 / 101 of the 340 / 264 / 267 false positives (r0 / r1 / r2), and 0 of the correct finds.
  If the model followed the line fully, v2's precision would move 0.200 / 0.244 / 0.246 -> 0.341 / 0.306 / 0.344 with recall
  unchanged (arithmetic on stored replies, not a prediction).
- Basis: `assetgen_meta/ASSET_DEFINITION.md` row 60 ("Bus-transaction ports are secondary"), which cites LAsset p2 and
  SAIF p2 and places this convention in the prompt. The bracketed shapes keep the processor's control record (no strobe, no
  acknowledge) outside it.

## What it breaks / how to read it

- Both phases read common.md, so this changes Phase 2's labels (its main target) and Phase 1's context. Compare v4 with v3,
  not with v2, to see this line alone.
- Falsified if bus record ports or fields are still primary in v4 runs, or if a correct find that is a plain port or an
  internal element behind a bus port drops below its v3 count (for example cfu csr_wdata_i, csr_we_i, start_i; trng
  fifo.re; hwspinlock sel and lock_q; imem addr and rden).
- Notebook: set `VERSION = "two_phase_v4"`. Runs go to `runs/two_phase_v4__v1/<model>__<effort>/r<k>`.
