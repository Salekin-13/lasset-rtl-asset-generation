# Study 3: the two-phase CSA to PIO prompt (10 to 19 October 2026)

- `two_phase_asset_identification.ipynb`: the final notebook. The working version `two_phase_p1o_first` on all 41
  modules; run cells off, checks and scoring on.
- `two_phase_ablation_log.ipynb`: re-scores every stored run of every version; its text is `logs/TWO_PHASE_ABLATION_LOG.md`.
- `lab/`: the kit. `prompts/two_phase_<version>/` (one README each, readings set before the run), `chain.py` (runner),
  `labkit.py`, `check_lab_prompt.py`, `cost_estimate.py`, `chain_tests.py`, `splits/`, `kit_data/`, `inputs/v1/` (RTL,
  closed set and diagram per module, built by `src/pio_diagram/`), `analysis/` (scorers and per-version scripts).
- Published from `lab/runs/`: the replies of the working version `two_phase_p1o_first` and of `two_phase_v7` (the
  scorer's self-test anchor), three runs each. The other version folders and the hand-off notes are local. Per-run
  counts of every version are in `lab/analysis/score_versions.json`; the per-module record of the working version
  (every hit, miss and false positive per run) is `lab/analysis/score_records_two_phase_p1o_first.csv`.

Until 20 October 2026 the lab was `final/pio/lab/`; `logs/LAYOUT.md` maps the old names.
