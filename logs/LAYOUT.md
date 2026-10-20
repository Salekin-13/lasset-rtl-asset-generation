# Repository layout and the 2026-10-02 move

On 2026-10-02 the loose files and folders in the repo root were grouped into five folders. Logs, pre-registrations,
notebook outputs and the convergence tables written before that date still use the old names. This page maps them.

## What moved where

| old path (root) | new path |
|---|---|
| `RTL_data/`, `RTL_heldout/` | `data/RTL_data/`, `data/RTL_heldout/` |
| `ground_truth/`, `LAsset_initial_results/` | `data/ground_truth/`, `data/LAsset_initial_results/` |
| `parsed_tuning18/`, `parsed_heldout26/`, `parsed_heldout_raw/` | `data/parsed_tuning18/`, `data/parsed_heldout26/`, `data/parsed_heldout_raw/` |
| `assets_*` run folders (22) | `runs/assets_*` (same names) |
| the 23 root `*.py` files (`eval_assets.py`, `rtl_parse.py`, `prompts*.py`, `icl_examples*.py`, ...) | `src/` (same names) |
| `finetuning_assetgen.ipynb`, `finetuning_assetgen_v2.ipynb`, `assetgen_meta.ipynb`, `lasset_step1.ipynb`, `lasset_evidence_layer.ipynb` | `notebooks/` (same names) |
| `ABLATION_LOG.md`, `ABLATION_LOG_V2.md`, `V02_HANDOFF.md`, `V02_REGISTRATION_DRAFT.md` | `logs/` (same names) |

Nothing else moved. `FINAL_NOTEBOOK.ipynb`, `README.md`, `final/`, `docs/`, `third_party/`, `assetgen_meta/`, `step1/`,
`step2/`, `bahavioral_patterns_of_assets/` and `blind_agent/` stay where they were. The subsystem folders have their
own `data/`-like subfolders (for example `bahavioral_patterns_of_assets/data/RTL_data/`); those did not move.

## How the move was made

1. **Renames only.** Every moved file kept its bytes. Git records the move as 1,449 renames at 100% similarity.
2. **Path strings.** In code that still runs (`FINAL_NOTEBOOK.ipynb`, `notebooks/lasset_evidence_layer.ipynb`, the
   final-version and diagnosis cells of `notebooks/assetgen_meta.ipynb`, and the modules they import), string
   literals that name a moved item gained a `data/`, `runs/` or `src/` prefix. Six unpinned modules that put the repo
   root on `sys.path` now put `src/` there instead (`final/final_pipeline.py`, `assetgen_meta/traced_inputs.py`,
   `cia_label.py`, `trace_digest.py`, `prompt_opt/read_final.py`, `hand_arms/score_hand_arm.py`). The two
   re-runnable notebooks move to the repo root when started in `notebooks/`.
3. **Records stay as they were.** Older notebooks and scripts whose inputs are not published were not edited. Their
   saved outputs, and the logs, keep the old names.

## The pre-registration pins

The three pre-registrations pin files by a hash of their bytes. A moved file keeps its hash. Seven pinned code files
were edited in path strings only: `src/eval_assets.py`, `assetgen_meta/meta_tools.py`, `assetgen_meta/lasset_layer.py`,
`assetgen_meta/fp_diagnosis.py`, `assetgen_meta/fault_reporter.py`, `assetgen_meta/trace_check.py` and
`step1/build_heldout_code_map.py`. Their hashes changed.

- **The tag `prereg-layout-before`** marks the last commit in the old layout, commit
  `5ebdfa0693761861f7fa39b7980ef1eeae03ac33`. There, all 40 pin rows of the three pre-registrations verify with the
  repo's own checks: `lasset_layer.verify_pins()`, `heldout_readings.verify_prereg()` and
  `prompt_opt/heldout_check.verify()`.
- **`python src/verify_layout_move.py`** (run from the repo root) checks the move against that commit.
  - It first tests itself on 15 planted cases.
  - It then checks that the tag points at that commit and that the commit is an ancestor of HEAD.
  - It checks that `HELDOUT_PREREG.md` and `prompt_opt/HELDOUT_CHECK_PREREG.md` are unchanged. It checks that
    `lasset_layer/PREREG.md` only gained the appended section 6, and that every row of section 6 matches its file.
  - It refuses to run if a pinned item has uncommitted changes.
  - It then checks each of the 40 rows. A row passes if the item is unchanged, or moved with the same bytes, or is
    a Python file that differs from the tagged bytes only in string literals. Each such literal must be rewritten by
    exactly one of the move's prefixes, for a name that moved. Outside string literals, everything must match byte
    for byte: code, comments, spacing and line endings. Inside an f-string, the code between braces must be identical.
  - It proves that nothing changed except the move's prefixes. It does not prove that every needed prefix was added;
    that was measured by re-running the notebooks (next section).
- **`assetgen_meta/lasset_layer/PREREG.md` has an appended section 6** with the twelve items at their new paths, so
  `verify_pins()` and `notebooks/lasset_evidence_layer.ipynb` still check pins at the latest commit. Section 5 is
  unchanged. `HELDOUT_PREREG.md` and `prompt_opt/HELDOUT_CHECK_PREREG.md` are not edited. Their own verifiers import
  modules that moved, so run them at the tag (below), or rely on `src/verify_layout_move.py`.

## Measured after the move

Each notebook ran in a fresh clone of the new layout and in a fresh clone of the tag, with no API key. Cell outputs
were compared with timings masked.

- `FINAL_NOTEBOOK.ipynb` as it was at the layout move (commit c696c76): 26 of 26 code cells gave the same text output
  in both layouts and as committed, and both figures were identical; the run changed no tracked file. Later versions
  add sections that use modules the tag does not have, so they are checked by re-running in a fresh clone of the new
  layout only.
- `notebooks/lasset_evidence_layer.ipynb` (kernel started in `notebooks/`): 5 of 5 code cells give the same output in
  both layouts and as committed. The pin check inside it passes.
- `notebooks/assetgen_meta.ipynb` cells 1, 64, 65, 66 and 68: the same in both layouts, except one label in cell 68,
  which now reads `runs/assets_opt_heldout_v1_r0`. The same label reaches two files under
  `assetgen_meta/fault_reporter/tuning_Claude_final/`. Cell 62 needs variables from cell 58, which calls the API, in
  both layouts.
- `src/verify_layout_move.py`: 40 rows, 0 failures. In a throwaway clone it stopped on each planted forgery: the tag
  moved, `HELDOUT_PREREG.md` edited, section 5 of `lasset_layer/PREREG.md` edited, and an uncommitted edit to a
  pinned file.

## Running record code

Record notebooks and scripts expect the old layout. Run them from a worktree of the tag, next to this clone:

```bash
git worktree add ../rtl-asset-audit-trail-old prereg-layout-before
```

These do not run in the new layout:
- the record notebooks in `notebooks/` (they do not move to the repo root);
- `final/build_convergence.py` (it also needs the run folders that are not published);
- `assetgen_meta/heldout_readings.py` and `assetgen_meta/prompt_opt/heldout_check.py`;
- the `src/` modules that still default to old root paths, such as `src/diagnose_step1.py`.

The pinned modules' command lines need `src/` on the import path in the new layout. Their own `sys.path` lines were
not edited, to keep the edits to path strings only. In Git Bash:

```bash
PYTHONPATH=src python assetgen_meta/lasset_layer.py --pins
```

In PowerShell, run `$env:PYTHONPATH = "src"` first, then the same `python` command. `--pins` prints the current hashes
for comparison with section 6 of `assetgen_meta/lasset_layer/PREREG.md`. The pass or fail check is
`python src/verify_layout_move.py`.

## Local copies

Only tracked files moved. In a working folder that also holds unpublished run folders at the root (`assets_*`), the
loaders now look in `runs/`. Move such folders into `runs/` to keep using them; `.gitignore` keeps them unpublished
there. A `.py` file left in the repo root would be imported before the one in `src/`, because the pinned modules put
the root first on `sys.path`. `final/final_pipeline.py` stops with an error if it finds one.

# The 2026-10-20 move

On 2026-10-20 the folders were grouped by study. Logs, notebook outputs, READMEs and the TIMELINE written before that
date use the names in the left column. The tag `layout-2026-10-20-before` marks the last commit in the old layout.

| old path | new path |
|---|---|
| `docs/` (TIMELINE.md, LAYOUT.md, TUNING_GUIDE.md, experiment_tracker.csv) | `logs/` (same names) |
| `final/` (the final notebook's code and outputs) | `map_pipeline/` (same names inside) |
| `final/pio/lab/` (the two-phase prompt lab) | `experiments/03_two_phase_csa_pio/lab/` (same names inside) |
| `final/pio/pio_pilot.ipynb` | `experiments/03_two_phase_csa_pio/two_phase_asset_identification.ipynb` (cleaned; outputs cleared) |
| `final/pio/pio_graph.py`, `pio_blocks.py`, `pio_inputs.py`, `pio_diagram.py`, `pio_flowfix.py`, `msim_check.py` (worktree only) | `src/pio_diagram/` |
| `notebooks/finetuning_assetgen.ipynb`, `finetuning_assetgen_v2.ipynb`, `recall_ablation_log.ipynb`, `precision_ablation_log.ipynb` | `experiments/01_prompt_baselines/notebooks/` |
| `notebooks/assetgen_meta.ipynb`, `lasset_step1.ipynb`, `lasset_evidence_layer.ipynb`, `map_ablation_log.ipynb` | `experiments/02_rtl_structural_analysis/notebooks/` |
| `notebooks/two_phase_ablation_log.ipynb` | `experiments/03_two_phase_csa_pio/` |
| `Diagrams/` (local) | `figures/` |

Nothing else moved. `src/`, `data/`, `runs/`, `assetgen_meta/`, `step1/`, `step2/`, `blind_agent/`,
`bahavioral_patterns_of_assets/` and `third_party/` stay: the three pre-registrations pin files by hash under those
names, and every module in them finds the repository root as its folder's parent. No pinned item moved, so
`python src/verify_layout_move.py` runs as before (only its docstring changed).

Edits made for this move, all path strings: `FINAL_NOTEBOOK.ipynb` (`final/` to `map_pipeline/`, `docs/` to `logs/`,
the notebook links); `map_pipeline/*.py` (the same two prefixes); the lab's scripts (`final/pio/lab` to its new path);
the six notebooks that moved (their root-finding cell, where it assumed `notebooks/` one level under the root); the five
short-form logs and the README. The lab's own root-finding lines (`LAB.parents[2]`) did not change: the lab sits three
levels under the root as before. Records (older logs, per-version READMEs, TIMELINE) were not edited.
