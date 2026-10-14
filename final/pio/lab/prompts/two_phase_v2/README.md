# two_phase_v2 — DRAFT (2026-10-12, not run, not approved)

Base: `two_phase_v1`. **Only `phase1.md` changes**: the Availability question (line 16) and six new bullets under "Rules:".
`common.md`, `phase2.md`, `phase1_user.md` and `phase2_user.md` are byte-identical to v1 (checked with `diff`).
`check_lab_prompt.py two_phase_v2`: clean (no corpus names, no banned words, no numeric hints).
Phase 1 system prompt: 35,814 characters, sha12 `df44fe84b87d` (v1: 33,961, `feac7243a8e8`). Phase 2: unchanged, `28a7f02c3a71`.

Purpose: cut the extra conceptual assets that Phase 1 produced in all three gpt-5.6-luna runs of v1 (63 / 67 / 77 per run;
clusters CX1–CX18 in `analysis/two_phase_v1__gpt-5.6-luna__high__r0-r2/THREE_RUN_FAILURES.md`, section 5.2).

## 1. Line 16, Availability

Old:
> Availability. Does this information gate an output port or the use of an input port, or would the operational behavior of the IP or the IC stop without it? If so, can an element of the IP make it unavailable? Focus on what a denial-of-service attack at the integration level could affect.

New:
> Availability. Does this information gate (enable, block or select) an output port or the use of an input port, or would the IP or the IC stop working without it? A clock input, a reset input, or a chain that only synchronizes or releases a reset does not qualify; a setting or request that controls a clock (an enable, a rate) does. If so, can an element of the IP block, disable or withhold it? Count only integration-level denial of service: a blocked port, a lost required transfer, or a halted IP or IC.

Changes from the user's draft, and why:
- "timing" and "initialization" are left out of the exclusion. 15 of the 111 reference elements are clock-rate settings,
  clock-enable requests, or timeout and reset registers (the prescaler, divider and baud fields, four clock-enable ports, the
  watchdog timeout, expiry, reset-cause and feed registers); a blanket "timing" exclusion would invite the model to drop them. The new line names what is
  out (clock input, reset input, reset synchronizer or release chain) and what stays in (an enable, a rate).
- "information", not "signals": Phase 1 names information; elements are Phase 2's job (Rules: "Describe a conceptual asset by
  what the information is, not by an element name").
- "gate" is kept: it is the white paper's own word for the availability question (P3164 p9–10), made specific with
  "(enable, block or select)".
- The line alone is not enough: 9 of the 26 clock/reset concepts in v1 also answered "yes" to integrity or to undermined
  behaviour, so the exclusion is repeated as a rule that covers every question (A1 below).

## 2. New rules (after the two existing bullets)

| Id | Rule (exact text) | Target | Basis |
|---|---|---|---|
| A1 | Clocks and resets. A clock input, a reset input, and a chain that only synchronizes or releases a reset (a reset shift register, a registered copy of a reset) are not conceptual assets under any question. A setting or request that controls a clock (an enable, a rate), and a decision that triggers a reset (a timeout, a violation), are judged as usual. | CX1, CX11 | **None published; user decision 2026-10-12.** Conflicts with `assetgen_meta/ASSET_DEFINITION.md` rows 61–62, which keep clock/reset inputs and reset generation as evaluation-layer conventions. Record it as a prompt-level convention. |
| A2 | Build-time values. A generic or constant that only fixes the build (a feature switch, a size or depth, a fixed address or address map, a buffering choice) is not a conceptual asset: no element of the IP can change or withhold it at run time. Name the run-time decision that uses it as its own concept instead (for example, which port an address selects, or which requester is granted). | CX2 | The rubric's second part (the RTL must show a mechanism; nothing changes a build-time value at run time) and step 2 (a decision is information of its own). |
| A3 | Pacing pulses. A tick, edge pulse or divider count made inside the unit only to pace another step is part of that step or of its rate setting (step 3), unless the unit outputs it. | CX4 | Step 3 ("an internal signal that only times one step of other information ... is part of the information it times"). |
| A4 | Forwarded transactions. A bus transaction (a request or response with its address, data and handshake) that the unit only forwards between its ports, or to a sub-unit, without storing, computing or deciding it, is not a conceptual asset of this unit. The decision about whether or where it passes is judged as usual. | CX5, CX17 | LAsset p2: system buses and ports that carry a primary's data are secondary assets; step 2 for the routing decision. |
| A5 | Bus handshake copies. A bus response acknowledge that only repeats or delays the bus request strobe, and a bus error flag tied to a constant, are not information of their own. | CX7 | Step 3 (it only times the transaction) and the rubric's mechanism (a constant cannot be changed). |
| A6 | Working values. The partial results inside a computation (a partial sum, product or round value, a synchronizer stage, a debiasing step) are part of the result they produce (step 3), not concepts of their own. | CX9 | Step 3; LAsset p2 (data held only in transit is secondary). |

Wording history (all tested): A5 first read "a response acknowledge ... the request strobe" and also removed a coprocessor's
done/valid concept (a correct one); "bus" was added. A6 first listed "an operand copy" (removed the protection unit's access
address, a correct find) and then a port clause (removed counters and decisions); it is now scoped to the kinds it lists.

## 3. Drafted but NOT added: rules with no basis, or that contradict the prompt or the reference's own picks

| Id | Draft text | Target | Why it is left out | Measured cost on v1 r0/r1/r2 (matched concepts removed; correct finds lost) |
|---|---|---|---|---|
| B1 | Control fields. Fields of one control register that software writes together are one concept, unless a field enables, locks, sets the rate of, or times out the unit. | CX3 | Copies the reference's own field choices; the Integrity question counts any configuration setting. | 0/0/0; 0/0/0 (but only 4 of 14 targets removed) |
| B2 | Register access. The address decode and the read and write enables of the unit's own register access are part of that access, not a concept of their own. | CX6 | Contradicts step 2; the reference keeps such decisions in other units. | 3/3/3; 3/3/3 |
| B3 | Sequencers. A state machine or counter that only steps the unit through its own transfer is part of that transfer, not a concept of its own. | CX8 | Contradicts step 2 ("the state of a state machine"). | 2/2/4; 2/1/3 |
| B4 | Received mode bits. A mode or status bit received from another unit and used only as a condition (a privilege level, a debug or trap flag) is not a concept of this unit. | CX10 | Contradicts the undermined-behaviour question (overrides, privileged modes). | 1/1/1; 1/1/1 |
| B5 | Buffer status. Fill flags and status bits of a buffer that are only read back are part of the data they describe. | CX12 | The reference keeps one buffer's fill status. | 0/0/0; 0/0/0 (1 of 12 targets removed) |
| B6 | Derived flags. A one-cycle flag derived from a request (a bypass choice, a failure bit, an output enable) is part of the controller state that sets it. | CX13 | Contradicts step 2 (enables and selects are information of their own). | 3/1/3; 5/2/5 |
| B7 | Processor state at the top level. The program counter, privilege level and trap or sleep state at a processor's top level are concepts of the sub-unit that holds them, not of the top level. | CX14 | Contradicts the prompt's own examples (common.md 2.4: privilege mode, program counter, debug-mode state). | 0/0/0; 0/0/0 |
| B8 | Memory arrays. A memory array is not a conceptual asset; the data read from or written to it is. | CX15 | P3164 p17–18 and SA-EDI count arrays; ASSET_DEFINITION row 62 keeps it an evaluation-layer convention. | 0/0/0; 0/0/0 (removed none of its 9 targets) |
| B9 | Serial transmit data. Data a serial controller only queues and shifts out is not a conceptual asset. | CX16 | The reference keeps transmit data in two other serial units. | 2/4/2; 3/3/2 |
| B10 | Stall inputs. A synchronized handshake input that only stalls an engine is part of that engine's operation. | CX18 | The reference keeps a clear-to-send input of the same shape. | 0/0/0; 0/0/0 |

B rules were checked by the prompt checker (clean) and by the same judges as the A rules.

## 4. Estimated effect (a filter on the stored v1 replies, not a re-run)

Two blind judges per module (40 agents, workflow wf_061af491-d28; narrowed A5/A6 re-judged in wf_5997168d-0f4) said which
rules would remove each of the 421 concepts of v1 r0–r2. `analysis/two_phase_v1__gpt-5.6-luna__high__r0-r2/rules_check/rule_effects.py`
counts the effect; the judges were not told which concepts match the reference.

| Run | Extra concepts removed (of extras) | Matched concepts removed | Reference concepts left uncovered | Structural precision v1 → filtered | Structural recall v1 → filtered (of 109) |
|---|---|---|---|---|---|
| r0 | 30 of 63 | 1 | 1 | 0.183 → 0.243 | 0.807 → 0.807 |
| r1 | 33 of 67 | 3 | 1 | 0.181 → 0.245 | 0.798 → 0.780 |
| r2 | 43 of 77 | 1 | 1 | 0.173 → 0.261 | 0.807 → 0.789 |

Corrected 2026-10-12: a first version of this table also counted 5 concepts that a judge removed only jointly with the old,
wider A6 wording (for example the r0 bus concept holding `alu_res`); with A6 narrowed they stay, so r0 loses nothing.

Correct finds the filter removes: bus `sel` and `port_sel` (r1, r2, via A2). In those runs the model listed them only under a
concept about build-time policy (no reference counterpart), so removing that concept removes them. Extra concepts carry 2–3 of
the 87–88 correct finds per run in v1 (r0: `alu_res`, `twi_sda_o`; r1: `sel`, `port_sel`, `twi_sda_o`; r2: `sel`, `port_sel`). A2's last sentence asks the model to name that decision as its own concept; a filter cannot show
whether it will, so only a run measures it. The uncovered reference concept is bus RC4 (downstream transaction strobe), in every
run, via A4; A4's last sentence keeps the routing decision.

## 5. What it breaks, and how to read the next run

- v1 runs stay the baseline. v2 writes to `runs/two_phase_v2__v1/<model>__<effort>/r<k>`; compare with gpt-5.6-luna v1 r0–r2,
  same model, effort `high`, three runs (about USD 0.8 and 8 minutes each).
- Read after the run: extra concepts per run and per CX cluster (target: about half of 63–77); Phase 1 recall (v1: 68 of 77 in
  every run); structural precision and recall; whether bus `sel`, `port_sel`, `alu_res` and RC4 are still found.
- The draft is **falsified** if the targeted clusters (CX1, CX2, CX4, CX5, CX7, CX9, CX11, CX17) keep more than half of their v1
  concepts, or if structural recall falls below 0.780 (the lowest filtered estimate) in two of the three runs.
