# Tuning a multi-stage pipeline — method

For LAsset Algorithm 1 lines 3–5. The point of this file is to stop effort going into a
stage that has no headroom, and to make every change attributable.

## The loop

1. **Ceiling** — per stage, if it were perfect, how much would the end metric move? This
   allocates effort. Do it before tuning anything.
2. **Error analysis** — inside the bottleneck stage, categorise the failures. This produces
   hypotheses; without it you are guessing.
3. **Pick the stage to fix at** — a defect is usually fixable at more than one stage. Choose,
   and say why.
4. **One arm per hypothesis, one variable per arm.**
5. **Measure against the noise floor**, paired on modules, with a CI.
6. **Record before and after** — `Expect:` written before the run.

Repeat from 2. Return to 1 only when a stage's measured contribution changes.

---

## 1. Ceiling analysis

For each stage, replace it with an oracle and re-measure. What you cannot do exactly,
bound: remove the stage entirely and see how far the metric falls.

**Result so far** (`src/stage_ceilings.py`, run against the manual GT on 15 modules):

| stage | ceiling | headroom | how it was measured |
|---|---|---|---|
| 4 `LLMparse` | recall 0.982 | **0.018** | fraction of GT elements present in the closed set at all — **two** are unreachable, both in `cache`: `inval_i` (is `inv_i` here) and `cache_o.cmd_dir` (no such field in this revision). Re-audited 2026-08-07; the earlier 0.991 counted only the first |
| 5 `LLMasset` | — | **~0.30** | everything between measured recall and 0.982 |
| 3 `SpecRAG` | not yet measured | unknown | see below |

Stage 5 has ~33× the available recall of stage 4. That is the allocation, and it will not
change until stage 5's recall approaches 0.99.

**Stage 3 is unmeasured and should be next.** Cheap bound: run one arm with the summary
removed from the user message. If the metric barely moves, the summary is not contributing
and tuning retrieval is wasted effort. If it collapses, it is load-bearing and worth
parameterising. This costs one arm and settles a whole stage.

**Recall headroom is not the only headroom.** A stage can be irrelevant to recall and
decisive for precision. Stage 4 is exactly that case — see below.

---

## 2. Error analysis

Take the bottleneck stage's failures and categorise them by hand. 30–50 sampled cases is
enough; the categories matter, not the count.

Two lists, kept separate because they have different causes:

- **FN** — in the closed set, in the ground truth, not emitted. Why not? Wrong objective
  assigned? Emitted at the wrong granularity? Never considered?
- **FP** — emitted, not in the ground truth. Which stage produced the candidate, and was it
  even a plausible one?

Attribute each to a stage. An earlier pass over 163 FPs attributed them: core prompt 72
(44%), post-filter 46 (28%), ICL examples 29 (18%), parser 16 (10%). That attribution is
what tells you which stage the next arm belongs to.

---

## 3. Choosing the stage to fix at

Most defects can be fixed in more than one place. Fixing early removes the candidate; fixing
late teaches the model to reject it. They are different, and the choice is testable.

Worked example — port-record fields:

> 959 of the 1,572 closed-set candidates (61%) are dotted fields of port records. Zero of
> them is a labelled asset in either reference.

| where | change | trade-off |
|---|---|---|
| stage 4 | stop expanding port records into the closed set | removes 61% of distractors outright; loses the ability to ever name one, and hard-codes a rule the model cannot override |
| stage 5 | instruct: name the port, not its field (A-03) | keeps the elements visible and reachable; costs prompt tokens and is only followed as well as the model follows instructions |

Fixing early is stronger but less reversible. Fixing late is softer and stays inside the
model's judgement. Run both as separate arms before deciding — that is the experiment.

**Rule: never fix the same defect at two stages in the same arm.** You will not know which
one worked, and they can cancel.

---

## 4. What is tunable, per stage

### Stage 3 — SpecRAG
Currently at the paper's parameters (chunk 1000 / overlap 200 / top-k 20, ada-002), so any
change is a deviation to justify.

Tunable: chunk size and overlap, top-k, embedder, query formulation, `SUMMARY_SYSTEM`.
Measure the stage first (§1) before touching any of them.

Note: summaries are generated once and reused by every arm, so re-tuning this stage
invalidates every prior result. Batch stage-3 changes; do not interleave them with stage-5
arms.

### Stage 4 — LLMparse
Recall headroom 0.009. **Do not tune this stage for recall.**

Precision headroom is large and unexploited. The closed set is the candidate list; its size
is the distractor count. `neorv32_bus` presents 808 candidates for 10 assets.

Tunable: record-expansion policy (all fields / signal-side only / none), whether to present
ports and signals separately or grouped by entity, the annotation prompts, whether
`function` text is included at all.

The parser itself is verified — fresh parse identical to cache on all 18 modules, zero
malformed elements. So what is tunable here is *presentation*, not extraction correctness.

### Stage 5 — LLMasset
Owns ~30 points of recall. Everything here is worth an arm.

Tunable: `ASSET_PRIMARY_CORE`, the ICL block, reasoning effort, output budget, the form RTL
arrives in, whether the summary and parsed blocks are present at all.

---

## 5. Screening before depth

With more than three or four factors, do not test combinations. Run one-factor-at-a-time
from a fixed baseline first — that is *k* arms for *k* factors and finds the main effects.
Only the factors that clear the noise floor earn a factorial follow-up for interactions.

An interaction worth suspecting here: a verbose core prompt may help with sparse examples
and hurt with worked ones, because the two compete for the same instruction budget.

---

## 6. Stop rules

Stop tuning a stage when any of these holds:

- Its ceiling headroom is below the noise floor. Nothing you do is measurable.
- Three consecutive arms return CIs straddling zero. The factor is not where the loss is;
  go back to §2.
- The change would need the tuning modules to be re-inspected. That is fitting to 15 modules,
  and it will not transfer to the other 26.

---

## 7. Budget

One arm = 18 modules × `REPEATS`. At `REPEATS = 3` that is 54 generation calls.

The ICL block is identical across all calls within an arm, so it hits the prompt cache at
roughly a 10× discount; the marginal cost of a repeat is dominated by output tokens, not by
the 30k-token system prompt. Arms that change the *core* prompt invalidate the cached prefix
for the ICL block that follows it — so batch core-prompt arms together.

Run A-00 (noise floor) first. If the sd comes back small, 2 repeats may be enough for the
rest, which is a third off every subsequent arm.
