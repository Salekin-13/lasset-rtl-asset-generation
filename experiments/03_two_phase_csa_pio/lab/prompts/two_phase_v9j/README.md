# two_phase_v9j: v9i + the control-unit bar sparing the unit's ports and output record + every keep block last in its step (built 2026-10-18; analysis/v10_diagnosis/make_v9j.py; PLAN_ISOLATE_CLUSTER_ORDER.md section 14)

**WORKING VERSION since 2026-10-18 (user decision D86).** System prompt sha12 27ad6995983b (Phase 1) / 155b0e00774d (Phase 2).
Measured on gpt-5.6-luna, high, inputs v1, three runs on all 41 modules (DECISION_LOG.md D84; verified independently):
held-out 26 pooled recall 0.848, precision 0.569; tuning_v2 0.853 / 0.593; tuning 15 0.865 / 0.697; heldout_v2 0.859 / 0.654.
Known: the block order deviates from "keep blocks last" (D85); two bars rest on the reference's convention (D86).

**FALLBACK since 2026-10-19 (D94): two_phase_v9n_place is the working version.**
