# paper_02 Workflow README

This directory contains the reproducible run scripts used for `paper_02`.
The workflow first appears in release `v1.1.0` and lives under:

- `examples/paper_runs/paper_02/`

All outputs are written to:

- `examples/paper_runs/paper_02/results/<run_name>/`

## Prerequisites

1. Build the simulator:

```bash
cmake -S . -B build
cmake --build build -j
```

2. Prepare Python environment for analysis/figures:

```bash
./examples/setup_env.sh
```

Notes:

- Scripts auto-call `ensure_examples_env`.
- `LIDMAS_SKIP_PY_DEPS=1` skips dependency installation, but analysis scripts still require Python + packages.

## Quick Start

Run core manuscript workflow (`01` to `06`):

```bash
./examples/paper_runs/paper_02/run_all.sh
```

Run core + advanced analyses (`07` to `14`):

```bash
LIDMAS_RUN_ADVANCED_ANALYSIS=1 ./examples/paper_runs/paper_02/run_all.sh
```

## Decoder Selection

Default decoder set (resolved by `common.sh`):

- `mwpm`
- `uf`
- `bp`
- `neural_mwpm`

Neural decoder behavior:

- Default model path: `examples/decoder_comparison/trained_model.json`
- Override with `LIDMAS_NEURAL_MODEL=/path/to/model.json`
- If model is missing, `neural_mwpm` is skipped with a warning

Override decoder list:

```bash
LIDMAS_DECODERS=mwpm,uf,bp ./examples/paper_runs/paper_02/01_pauli_baseline.sh
```

Also accepted (if explicitly requested): `stub`.

## Native GKP Defaults

Used by GKP runs unless overridden:

- `LIDMAS_GKP_GATE=0.005`
- `LIDMAS_GKP_MEAS=0.01`
- `LIDMAS_GKP_IDLE=0.005`
- `LIDMAS_GKP_LOSS=0.005`
- `LIDMAS_GKP_LOSS_MAP` unset by default

Sweep defaults in GKP-focused scripts:

- `sigma_start=0.05`
- `sigma_end=0.35`
- `sigma_step=0.05`

## Script Map

- `01_pauli_baseline.sh`
  - Purpose: fixed-distance Pauli comparison
  - Defaults: `d=5`, `trials=3000`, `p=0.03:0.01:0.12`
  - Outputs: `results_<decoder>.csv`, `combined.csv`, `figure_pauli_baseline.*`, `table_pauli_baseline.{csv,md}`
- `02_gkp_baseline.sh`
  - Purpose: fixed-distance native GKP comparison
  - Defaults: `d=5`, `trials=1500`, `sigma=0.05:0.05:0.35`
  - Outputs: `results_<decoder>.csv`, `combined.csv`, `figure_gkp_baseline.*`, `table_gkp_baseline.{csv,md}`
- `03_gkp_multidistance.sh`
  - Purpose: native GKP multi-distance comparison
  - Defaults: `d=3,5,7`, `trials=1500`, `sigma=0.05:0.05:0.35`
  - Outputs: per-decoder CSVs/figures, `combined.csv`, `table_gkp_multidistance.{csv,md}`
- `04_pauli_threshold.sh`
  - Purpose: Pauli threshold/scaling summary
  - Defaults: `d=3,5,7`, `trials=4000`, `p=0.04:0.01:0.12`, `bootstrap=200`
  - Outputs: per-decoder `results_*.csv`, `scaling_report_*.md`, `scaling_summary_*.json`, per-decoder figures, aggregated threshold summary tables
- `05_gkp_threshold.sh`
  - Purpose: GKP threshold/crossing/scaling summary
  - Defaults: `d=3,5,7`, `trials=1500`, `sigma=0.05:0.05:0.35`, `bootstrap=200`
  - Outputs: per-decoder `results_*.csv`, per-decoder figures, `combined.csv`, crossing summary tables, scaling summary tables (or placeholder if no scaling JSON)
- `06_parallelization.sh`
  - Purpose: serial vs threaded fidelity and throughput (+ optional Pauli GPU leg)
  - Defaults: `decoder=mwpm`, `d=5`, `trials=4000`, `threads=4`
  - Runs: `pauli_serial`, `pauli_threaded`, optional `pauli_gpu`, optional `gkp_serial/gkp_threaded`
  - Outputs: `timings.csv`, `table_parallelization.{csv,md}`
- `07_decoder_pareto.sh`
  - Purpose: runtime vs LER Pareto front
  - Defaults: `d=5`, `trials=1500`, `sigma_ref=0.20`
  - Outputs: `timings_decoder_pareto.csv`, `table_decoder_pareto.{csv,md}`, `figure_decoder_pareto.*`
- `08_crossing_bootstrap.sh`
  - Purpose: crossing-stability bootstrap (`d3/d5`, `d5/d7`)
  - Defaults: `bootstrap=1500`
  - Inputs: uses `results/05_gkp_threshold/results_<decoder>.csv` (auto-runs `05` if missing)
  - Outputs: `table_crossing_bootstrap.{csv,md}`, `figure_crossing_bootstrap.*`
- `09_distance_gain_heatmap.sh`
  - Purpose: distance-gain heatmap from multi-distance results
  - Inputs: `results/03_gkp_multidistance/combined.csv` (auto-runs `03` if missing)
  - Outputs: `table_distance_gain.{csv,md}`, `figure_distance_gain_heatmap.*`
- `10_noise_ablation.sh`
  - Purpose: one-factor GKP component ablation (`gate`, `meas`, `idle`, `loss`)
  - Defaults: `trials=1200`, `d=5`, `sigma_ref=0.20`, levels `0.0000,0.0025,0.0050,0.0100`
  - Outputs: manifest + per-case result CSVs, `table_noise_ablation.{csv,md}`, `figure_noise_ablation.*`
- `11_rank_stability.sh`
  - Purpose: decoder rank stability bootstrap
  - Defaults: `bootstrap=1500`
  - Inputs: `results/02_gkp_baseline/combined.csv` (auto-runs `02` if missing)
  - Outputs: `table_rank_stability.{csv,md}`, `figure_rank_stability.*`
- `12_effect_size.sh`
  - Purpose: pairwise bootstrap effect sizes
  - Defaults: `bootstrap=2000`
  - Inputs: `results/02_gkp_baseline/combined.csv` (auto-runs `02` if missing)
  - Outputs: `table_effect_size.{csv,md}`, `figure_effect_size_heatmap.*`
- `13_threading_fidelity.sh`
  - Purpose: threaded-vs-serial fidelity diagnostics
  - Inputs: `results/06_parallelization/timings.csv` (auto-runs `06` if missing)
  - Outputs: `table_threading_fidelity.{csv,md}`, `figure_threading_fidelity.*`
- `14_critical_window.sh`
  - Purpose: dense sigma-window zoom + local crossing estimates
  - Defaults: `trials=2500`, `d=3,5,7`, `sigma=0.08:0.02:0.24`
  - Outputs: `results_<decoder>.csv`, `combined.csv`, `table_critical_window_crossings.{csv,md}`, `figure_critical_window_zoom.*`

## Environment Variables

Common controls (many scripts):

- `LIDMAS_DECODERS`
- `LIDMAS_NEURAL_MODEL`
- `LIDMAS_SEED`
- `LIDMAS_THREADS`
- `LIDMAS_TRIALS`
- `LIDMAS_DISTANCES`
- `LIDMAS_D`
- `LIDMAS_P_START`, `LIDMAS_P_END`, `LIDMAS_P_STEP`
- `LIDMAS_SIGMA_START`, `LIDMAS_SIGMA_END`, `LIDMAS_SIGMA_STEP`
- `LIDMAS_SCALING_BOOTSTRAP`

Parallelization (`06_*`):

- `LIDMAS_PAR_DECODER`
- `LIDMAS_PAR_D`
- `LIDMAS_PAR_TRIALS`
- `LIDMAS_PAR_SEED`
- `LIDMAS_PAR_THREADS`
- `LIDMAS_PAR_INCLUDE_GKP`
- `LIDMAS_PAR_INCLUDE_GPU`
- `LIDMAS_PAR_P_START`, `LIDMAS_PAR_P_END`, `LIDMAS_PAR_P_STEP`
- `LIDMAS_PAR_SIGMA_START`, `LIDMAS_PAR_SIGMA_END`, `LIDMAS_PAR_SIGMA_STEP`

Advanced analysis controls:

- `07`: `LIDMAS_PARETO_TRIALS`, `LIDMAS_PARETO_D`, `LIDMAS_PARETO_SIGMA_START`, `LIDMAS_PARETO_SIGMA_END`, `LIDMAS_PARETO_SIGMA_STEP`, `LIDMAS_PARETO_SIGMA_REF`, `LIDMAS_PARETO_SEED`, `LIDMAS_PARETO_THREADS`
- `08`: `LIDMAS_CROSS_BOOTSTRAP`, `LIDMAS_CROSS_SEED`
- `10`: `LIDMAS_ABLATION_TRIALS`, `LIDMAS_ABLATION_D`, `LIDMAS_ABLATION_SIGMA_REF`, `LIDMAS_ABLATION_SIGMA_STEP`, `LIDMAS_ABLATION_SEED`, `LIDMAS_ABLATION_THREADS`, `LIDMAS_ABLATION_LEVELS`
- `11`: `LIDMAS_RANK_BOOTSTRAP`, `LIDMAS_RANK_SEED`
- `12`: `LIDMAS_EFFECT_BOOTSTRAP`, `LIDMAS_EFFECT_SEED`
- `14`: `LIDMAS_CRIT_TRIALS`, `LIDMAS_CRIT_DISTANCES`, `LIDMAS_CRIT_SIGMA_START`, `LIDMAS_CRIT_SIGMA_END`, `LIDMAS_CRIT_SIGMA_STEP`, `LIDMAS_CRIT_SEED`, `LIDMAS_CRIT_THREADS`

GKP channel controls (used where mode is GKP):

- `LIDMAS_GKP_GATE`
- `LIDMAS_GKP_MEAS`
- `LIDMAS_GKP_IDLE`
- `LIDMAS_GKP_LOSS`
- `LIDMAS_GKP_LOSS_MAP`

Master switch:

- `LIDMAS_RUN_ADVANCED_ANALYSIS=1` enables runs `07` to `14` in `run_all.sh`

## Examples

Run only the Pauli baseline with fewer trials:

```bash
LIDMAS_TRIALS=500 ./examples/paper_runs/paper_02/01_pauli_baseline.sh
```

Run GKP baseline without neural decoder:

```bash
LIDMAS_DECODERS=mwpm,uf,bp ./examples/paper_runs/paper_02/02_gkp_baseline.sh
```

Run parallelization study with BP and 8 threads:

```bash
LIDMAS_PAR_DECODER=bp LIDMAS_PAR_THREADS=8 ./examples/paper_runs/paper_02/06_parallelization.sh
```

Run full workflow including advanced analyses:

```bash
LIDMAS_RUN_ADVANCED_ANALYSIS=1 ./examples/paper_runs/paper_02/run_all.sh
```
