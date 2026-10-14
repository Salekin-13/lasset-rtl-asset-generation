# two_phase_v7: v6d + five narrowings to win back v6's lost recall: the FINAL prompt (2026-10-13)

**Status: final prompt (user decision 2026-10-13).** Ran 3 times.

| | Precision (correct ÷ listed) | Recall (correct ÷ 109 per run) |
|---|---|---|
| v7 | .630 / .563 / .656; pooled 267/435 = 0.614 | .844 / .817 / .789; pooled 267/327 = 0.817 |
| v6 | pooled 0.620 | pooled 0.780 |
| v5f (6 runs) | pooled 0.416 | pooled 0.827 |

- All readings below held.
- 6 of the 10 lost elements came back in 2 or more runs.
- Two watch-list false positives appeared: bus arbiter.state and bus locked.
- The text below was written before the run.

## What it is

- **Base:** two_phase_v6d, the final condensed prompt. It is level with v6 in 3 runs: precision 0.617 vs 0.620, recall
  0.774 vs 0.780.
- **The user's request (2026-10-13):** add the narrowings a second session derived from the v6 run, keeping the added
  rules condensed. Their purpose is to address v6's recall drop against v5f:
  - pooled recall fell from 0.827 (v5f, 6 runs) to 0.780 (v6, 3 runs), p 0.036 in that session's permutation test;
  - pooled precision rose from 0.416 to 0.620;
  - 10 established elements were lost.

  The source is `analysis/two_phase_v6__gpt-5.6-luna__high__r0-r2/V6_RESULTS.md` ("Recommendations for the
  narrowing"). The pasted summary was checked against it.
- **The common cause found there:** the model skips exceptions that follow a rule's main sentence in a trailing "Judged
  as usual" or "Not covered" list. Each fix puts the exception inside the main sentence, described by role.

| Rule | Change | Words added |
|---|---|---|
| CX2.U3b (sequencing state) | the coprocessor and peer-clocked debug-port scope first; the grant (a state naming which requester holds a shared path, with the select and strobe it drives), reservation, timeout/timer counts, self-generated-bit counts and their flags moved into the main sentence; the trailing lists deleted; the four pointer sentences given the coprocessor exception; in a coprocessor, the state machine's state is kept as a concept and its step counter held in it | +66 |
| CX4.TF1 (transaction flags) | "a register read by a choice between requesters" moved into the main sentence; requests held until served next to the current grant | +10 |
| CX1-ACF (access command fields) | the record-port condition in the head and in its Operation selectors pointer; an address picking a word of a memory array is the access address | +42 |
| P11.5 (held addresses) | "next-value wire" defined; a wire only copying part of an access's address field is that address's own element | +74 |
| LS1 (label rule) | a line saying it only adds primaries and never demotes a port | +32 |

- **Built by:** `analysis/prompt_builds/v7/make_v7.py`, from the edits of wf_88588443-cb4 (one drafter and one checker
  per rule; edits.json).
- **Review fixes:** one combined read-through of all five rules found six wording problems, now fixed (the "REVIEW"
  entry of edits.json, -5 words):
  1. a unit shifting in bits it generates is exempt from sequencing state as a whole again, as in v6d (the first
     draft had shrunk it to its bit-adding count);
  2. "its internal busy and done flags" replaces "those flags", which could have reached the timeout flags;
  3. "a test choosing between requesters which one is granted", so a busy-state test that only keeps the current
     requester granted does not free a lock copy;
  4. the pacing pointers merge only the busy-state count the rule merges;
  5. the keep-the-state sentence refers back to that busy state;
  6. the held-line exception reads "an element this rule does not bar".
- **Checks passed:**
  - each edit's old text found exactly once;
  - the project prompt checker (corpus identifiers, banned words, numeric hints);
  - `chain.new_format`;
  - OUTPUT sections identical to v6d;
  - every sentence the two phase files shared in v6d still shared.
- **Words:** phase1.md 5,963 (v6d 5,866, v6 6,200); phase2.md 7,573 (v6d 7,451, v6 7,863). It is still shorter than
  v6.
- **Shas:** Phase 1 `be3b3faab49b`, Phase 2 `6e414c09e397`. Both change, so this version needs full runs.
- **Label:** the five rules are narrowings of restrictions labelled "user decision: reference convention" (v6 README).
  They hand back to the ordinary rules elements those restrictions reached beyond their wording.

## Readings (set before the run; compare with v6 r0-r2, v6d r0-r2 and v5f r0-r5, never pooled across versions)

Read with `analysis/two_phase_v7__gpt-5.6-luna__high__r0-r2/compare_v7.py`. Its self-test reproduces v6 86/83/86 and
v5f 91/85/92/94/91/88 correct finds.

1. **Recovery:**
   - the 10 elements v6 lost are bus a_req, b_req, state#1 and state#2, cpu_cp_cfu csr_addr_i and csr_we_i,
     cpu_cp_muldiv ctrl.state and valid_o, imem addr, and sys enable_i;
   - at least 5 found in 2 or more of 3 v7 runs supports the narrowing. **Fewer falsifies it.**
2. **Recall:**
   - 2 or more runs below 0.761 (v6's lowest run) **falsifies** "the narrowing does not cost recall";
   - 2 or more runs above 0.789 (v6's highest run) supports a gain.

   Phase 2 alone moves a run by 0-5 correct finds on fixed concepts (measured 2026-10-13), so smaller differences are
   not read as effects.
3. **Precision:** 2 or more runs below 0.601 (v6's lowest run) **falsifies** "the narrowing keeps v6's precision".
4. **Watch list:** the false positives the v6 diagnosis expected to come back:
   - the arbiter, cache-controller and serial-engine state registers and busy flags;
   - the switch's locked bit;
   - the gateway's keeper busy and lock;
   - the cache tag and index.

   compare_v7.py counts listed non-reference elements with such names against v6. This is an approximate name
   pattern.
5. **Module-level test** against v6 and v6d (losses cluster by reply): reported, not a falsifier.
6. **Format:** zero slips.

## What it breaks

- Nothing in the reply format.
- **Some precision may come back:** this is the stated cost (reading 4).
- Checks keyed on v6d's wording of these five rules must use the new wording.

## How to run (paid; the user decides who sends it)

Notebook cell 9 runs v7 for 3 runs. Both phases are new, so this is a full run. Restart the kernel and run cell 1 first.

**Cost estimate:** about USD 2.1. v6's 3 runs cost USD 2.08 from the stored usage (Phase 1 0.81, Phase 2 1.28). v7's
prompts are about 2% longer than v6d's.
