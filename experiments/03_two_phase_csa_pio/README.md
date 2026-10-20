# Study 3: the two-phase CSA to PIO prompt (10 to 19 October 2026)

- `two_phase_asset_identification.ipynb`: the final notebook. The working version `two_phase_p1o_first` on all 41
  modules; run cells off, checks and scoring on.
- `two_phase_ablation_log.ipynb`: re-scores every stored run of every version; its text is `logs/TWO_PHASE_ABLATION_LOG.md`.
- `lab/`: the kit. `prompts/two_phase_<version>/` (one README each, readings set before the run), `chain.py` (runner),
  `labkit.py`, `check_lab_prompt.py`, `cost_estimate.py`, `chain_tests.py`, `splits/`, `kit_data/`, `inputs/v1/` (RTL,
  closed set and diagram per module, built by `src/pio_diagram/`), `analysis/` (scorers and per-version scripts).
- Not published: `lab/runs/` (the model replies) and the hand-off notes. Per-run counts are in
  `lab/analysis/score_versions.json`.

Until 20 October 2026 the lab was `final/pio/lab/`; `logs/LAYOUT.md` maps the old names.
