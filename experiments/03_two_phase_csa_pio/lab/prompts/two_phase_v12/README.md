# two_phase_v12: v11h + the rule fixes that passed alone + N12 (built 2026-10-17, not run)

Diagnostic candidate for the next Phase 1 version. Plan, readings and cost: analysis/v10_diagnosis/PLAN_V12.md. Built by
analysis/v10_diagnosis/make_v12.py from two_phase_v11h (v10 + F1 + F2, v10's Phase 2).

- Access command fields, both phases: new_rules/rule_texts_v11r2.json (luna rule-alone PASS, D67). Basis: principle
  (drafter), partly following the reference.
- Port buffers, Phase 1 only: rule_texts_v11r3.json (PASS over its re-test cells, D69). Phase 2 keeps v11h's block.
  Basis: partly a reference convention (user decision under D11 needed before adoption).
- Sequencing state: Phase 1 rule_texts_v11r3.json (0.100, contradictions in 2 modules, D69); Phase 2 v11r2 (PASS, D67).
- Command bit copies (N12), both phases: rule_texts_v11q.json; user decision D66, labelled "user decision: reference
  convention" (D11), partly principle (2.6 carrier sentence).
- Pacing pulses and Operation selectors: unchanged from v11h (their rewordings failed alone).
