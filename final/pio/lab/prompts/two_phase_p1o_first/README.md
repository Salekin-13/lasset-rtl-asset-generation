# two_phase_p1o_first: A with the debug bar's Phase 1 block as the first rule block (built 2026-10-19; analysis/v10_diagnosis/make_p1_order.py; PLAN_P1_ORDER.md Tier 1)

**Tier 1 (D99):** Phase 1 located share 0.825 (A 0.836, p 0.49), bar fires 3/3. **Tier 3 (D102):** both phases, held-out 26 x3: 470 / 682 / 561 -> recall 0.838, precision 0.689 (A 0.843 / 0.662). Passes the Tier 3 cut. Caveat D100: the bar's slot lines are unindented in this version. Not the working version.

**WORKING VERSION since 2026-10-19 17:05 (user decision D103); fallback two_phase_v9n_place.** System prompt sha12 b4c962e16261 (Phase 1) / 021cc963702d (Phase 2, identical to v9n_place). Measured on the held-out 26 only, three runs, verified: recall 0.838, precision 0.689 (v9n_place 0.843 / 0.662; v9j 0.848 / 0.569). Known: the debug module's reset-request output is never found (fix built as two_phase_p1o_first2, untested); slot lines of the bar unindented (D100); tuning groups and all 41 unmeasured.
