# Prompt version two_phase_v1 (written 2026-10-10/11, not run)

Two calls per module (prompt chaining). Not sent to the model: this README.

| Call | System prompt | User message |
|---|---|---|
| Phase 1, conceptual assets (CSA rubric) | `common.md` + `phase1.md` | `phase1_user.md` with {module} {rtl} {closed_set} {diagram} |
| Phase 2, structural assets (PIO) | `common.md` + `phase2.md` | `phase2_user.md`, the same plus {concepts} = Phase 1's "conceptual assets" list |

Assemble and check: `python final/pio/lab/check_lab_prompt.py two_phase_v1` (corpus identifiers, numeric hints,
comment use, "only the final JSON object"; a planted-error self-test runs first).
Inputs: `final/pio/lab/inputs/v1` (see its README).

## Where the text comes from

| Section | Source |
|---|---|
| Task, 1 (inputs) | Written for this prompt from the input builders (`pio_inputs.py`, `pio_blocks.py`); each statement checked against all 43 modules by review agents |
| 2.1-2.8 | The user's candidate definitions 1.1-1.8, edited where listed below |
| 2.9 | The user's 1.9, edited where listed below |
| 3 | P3164 white paper p9 (assume the objectives; zero context) |
| 4.1 | SA-EDI Table 2 asset types (via the user's 2.1), qualifiers from SA-EDI |
| 4.2 | SAIF p2 list of primary-asset examples and SAIF's case study (p5-6); four items of the user's list removed, see below |
| 4.3 | Nath & Tan (ISQED 2025) Alg. 1 and p3-4, via the user's 2.3, hedges restored |
| 4.4 | The user's 2.4, cut to the parts a published source supports, see below |
| Phase 1 rubric | P3164 p9 questions 1-4 (the user's rubric), split into a judgement part and a mechanism part |
| Phase 2 questions | P3164 p19 PIO questions (the user's text); points = blocks (P3164 p19, p21) |

## Changes from the user's candidate text

The numbered list the reviewers worked from is in the session notes; in short:

1. "Attack points" bullet of 1.9 left out: standing user decision 2026-09-19, never put P3164's "ports are attack
   surface" view into a prompt.
2. 1.5: instances, generics and ROMs are not in the closed set, so they are reported through closed-set elements.
3. Phase 2 "focus on Instructions and Data" (P3164's CPU example) -> each conceptual asset from Phase 1.
4. Phase 2 points are diagram blocks (P3164 p19, p21), plus concurrent assignments to output ports that belong to
   no block. Ports are where the walk starts and ends; a port is still reportable as a structural asset (user 1.5;
   decision 2026-09-19 "ports stay").
5. CSA rubric questions are asked of each piece of information, as two-part tests (judgement = P3164 p9's own
   second sentences; mechanism = what the RTL shows). Section 3 says the assumption picks the objective to test.
6. Verilog terms -> VHDL (no "?:"; generate conditions; generics).
7. (Withdrawn 2026-10-11.) The rule that kept clocks and resets out of flows, walks and assets is removed: it has no
   theory basis, and `assetgen_meta/ASSET_DEFINITION.md` row 61 already puts "clock and reset inputs are not assets"
   in the evaluation layer as a reference convention. Measured 2026-10-11: 0 of the 296 reference entries that
   resolve in the closed sets (300 entries, 41 modules) is tagged clock or reset; the reference does list
   clock-related and reset-related elements that are not clocks or resets themselves (clock-enable outputs, a
   prescaler setting, a reset cause, a reset request, a reset output). Clocks and resets are now judged by the
   definitions; the walk does not follow them because they carry no value (2.2).
8. Phase 2 answers "no" to a question whose objective Phase 1 did not list.
9. 2.6 primary = where the value is stored or computed, where it crosses the unit boundary whole (input port that
   sets it, output port that returns it unmixed, signal to/from an instance), or the element holding a decision.
   Elements that only pass it on are carriers (secondary, direction a). Same as `assetgen_meta/ASSET_DEFINITION.md` s.2.
10. 2.7(b) also covers an element that decides whether p's value is released (a confidentiality threat); a direction
    counts only for an objective the conceptual asset has.
11. 2.9: authorization = the conditions the RTL itself checks; an unchecked access is the designed access. At points
    that store or set the asset the designed access still counts (holder rule); elsewhere intended behavior alone
    is not a violation. The cache example was removed because the holder rule reverses P3164's own DCache integrity
    answer (p22); basis for the holder rule = the measured PIO v1 pilot failure.
12. Phase 1 also names internal state and each enable/select/override/lock as information of its own.
13. Black-box rule for instances of another IP (one instance deep); two named exceptions to "never from a name".
14. Phase 2 output groups ports that differ only by an index ("same role").
15. Indicator texts aligned with their sources (SA-EDI qualifiers, Nath & Tan hedges); 4.2 heading says "each for its
    own conceptual asset".
16. Every port in a concept's "enters through" / "leaves through" is a structural asset of it (2.6 makes the setting
    input port and the returning output port primary), even when every answer at its point is "no".
17. An internal signal that only times one step of other information (an increment pulse, a started flag) is part
    of that information, not a conceptual asset of its own.
18. Clock and reset are defined by the closed-set tags; a test inside the clock-edge arm is a condition, whatever its
    name. An index that picks what is read or written is a flow of its value.

## Review before any run (2026-10-10/11, Claude agents, read-only)

Each round: reviewers with different lenses (two of them worked real modules by hand as the model would), then two
independent verifiers per reviewer tried to refute every finding; a finding counts when both confirm it.

| Round | Agents | Findings | Confirmed by both | Of those, high or medium |
|---|---|---|---|---|
| 1 (draft) | 15 | 72 | 61 | 34 |
| 2 | 15 | 89 | 76 | 33 |
| 3 (high/medium only) | 9 | 21 | 18 | 18 |

All confirmed findings were applied after each round. Round 3's fixes have not been reviewed again. The open edge cases
are in Phase 2's walk (how arrows into output ports and through instances are judged).

A reviewer's hand dry run of `neorv32_wdt` on the round-3 text (not a model run): 10 conceptual assets, 30 points,
16 distinct elements labelled primary for some conceptual asset.

## What to read after the first run (fill in before running)

- Precision and recall of the primary rows (strict scorer, 111 tuning entries), and the port-field convention row
  separately. Comparison rows on the same executor: final prompt and PIO run 0.
- Phase 1: kept vs "considered, not kept" per module (does the rubric drop anything?), and the share of concepts with C.
- Phase 2: points per concept, primaries per concept, share of primaries that are port fields.
- What this breaks: nothing earlier. New folder; runs of this version are not pooled with any other version.

## Indicator items checked against the published PDFs (2026-10-11)

The user's indicator lists came from a Claude message, so every item of 4.2 and 4.4 was checked against the 21
published PDFs in `E:\jobs\ff` (this project's own "Reading RTL for Assets" and "Parser Failure Atlas" excluded as
circular). Five search agents, two refuters per group; workflow `wf_a83c50ec-aa1`.

4.2, kept: the six items of SAIF's list of primary-asset examples (SAIF p2, cited there to Basak et al. 2015, which is
not in the folder; SAIF's own wording used), and the program counter as SAIF's case-study primary asset (p5-6).
4.2, removed: lock bits (no source names them as an asset; SA-EDI's watchdog example uses the lock bit as the
protection mechanism and violation condition of the real asset), memory-protection settings (no PDF names them),
the privilege mode (only inside SAIF's "configuration bits for operational and privilege modes", already kept),
the debug enable (no source names it as an asset; debug appears as an attack path or mode).

4.4, kept as supported: debug/test/bypass/override/mode-select logic (P3164 CSA Q4; worded as "the asset is usually
what this logic can reach"), data-dependent timing (P3164 Table 3, Hu et al. constant time), lock or permission gates
(SA-EDI condition, SAIF secondary), state machines (SA-EDI Control type, SAIF, LASP), reset paths that clear
protection state (BugWhisperer, LASP, as weaknesses). Narrowed to the supported part: multiplexers (P3164 GPIO; "OR-
merges" and "several sources reach one destination" have no source), shared structures (caches, buffers, register
files; "FIFOs" and "stateful" not named by any source), generics (SA-EDI lists parameters linked to an asset; no
source says they remove protection logic; "generate statements" not named). Removed: registers not cleared on reset
("data remanence" appears in no source, only as weakness checks).

4.1 (SA-EDI Table 2) and 4.3 (Nath & Tan) were checked against their sources in review round 1.

## Information flow vs diagram notation (2026-10-11)

Measured on all 43 modules' diagrams (self-test on hand-read wdt lines 130, 131-132, 144): 88 of 1,171 bracketed
"==>" arrows list a decide-only element; 24 of 424 bracketed "-->" arrows list an index; 70 of 245 "==>" arrows into
instance blocks list only clock- or reset-tagged elements. 2.2 and 1(c) now say this. The definitions write flows in
words ("flows to"), never as "->", so they cannot be read as the diagram's "-->". "Listed elements" (the brackets)
and "carries" (2.2) are separate terms. A check workflow (`wf_8146d257-0c3`, 2 checkers + 4 refuters) confirmed 6 more
mismatches (instance arrows into output ports, ports a block assigns itself, release deciders); all applied.
Known input issue left for inputs v2: every diagram.txt's key line after ARROWS ("==> a value moves; --> only
decides; [the elements the arrow carries]") is looser than 1(c); the prompt says 1(c) and 2.2 win.

## Runner, converter, cost (built 2026-10-11, not run)

- `lab/chain.py`: Phase 1 -> Phase 2 per module, schema and fact checks, converter to the scorer's format (primary
  rows; "same role" expanded; one row per element; objective C > I > A), readings with denominators. Pay-once OpenAI
  executor (background mode, request id saved before waiting, reply written before the id is dropped, no automatic
  re-send of a reply cut short, interrupt sends nothing new). Claude-agent executor through `pio_run.file_call`.
  Tests: `python final/pio/lab/chain.py selftest` (17 checks) and `python final/pio/lab/chain_tests.py` (13 checks,
  fake OpenAI client). Reviewed by two agent rounds (16 + 15 confirmed defects, fixed and re-tested).
- `lab/cost_estimate.py`: input tokens from the o200k pre-token split, calibrated on the final prompt's measured
  gpt-5.4 run (ratio 1.0724); output tokens borrowed from that run (no measurement for this prompt yet). On
  2026-10-11: 30 calls, about 768K input tokens, largest call about 88K; gpt-5.4 about USD 12.6-13.1 at the borrowed
  output rate, 6.7-25.4 over half to twice that rate. A pilot on two modules (`pilot()`) replaces the borrowed figure.
- Notebook `final/pio/pio_prompt_lab.ipynb` cells 10-13; cell 1 now changes to the repository root (the scorer reads
  data/ relative to the working folder; from the notebook folder it found no modules).
- Not handled: a create request whose reply is lost in transit is sent again on the next run; two processes running
  the same rep at the same time can send a request twice.
