# paper_04 Workflow README

This directory contains the reproducible workflow for `paper_04`:

- `PennyLane/Qiskit/Cirq vs LiDMaS+ with code-family-aware replay benchmarking`

Workflow root:

- `examples/paper_runs/paper_04/`

Outputs:

- `examples/paper_runs/paper_04/results/<run_name>/`

## Goal

Build decoder request streams from three independent software stacks plus a LiDMaS+
reference backend, with optional code-family selection:

- `surface`: repeated-round surface-code stabilizer circuits
- `gkp`: repeated-round digitized GKP-style syndrome streams

Datasets per run:

1. PennyLane (`decoder_requests_pennylane.ndjson`)
2. Qiskit (`decoder_requests_qiskit.ndjson`)
3. Cirq (`decoder_requests_cirq.ndjson`)
4. LiDMaS+ classical reference (`decoder_requests_lidmas_reference.ndjson`)

Each request stream is generated from repeated stabilizer-measurement rounds, then
replayed through the same LiDMaS+ decoder matrix (MWPM, UF, BP, optional neural MWPM).

## Repeated-Round Model

The generator implements planar surface-code geometry aligned with LiDMaS+:

- data qubits: `2*d*(d-1)`
- X checks: `d*d`
- Z checks: `(d-1)*(d-1)`

For each request line:

1. evolve a Pauli frame over multiple rounds using configurable data noise,
2. run framework-specific stabilizer extraction circuits for X and Z checks,
3. apply measurement noise,
4. emit detector-style events from round-to-round syndrome changes.

Default export is `Z` events only (`LIDMAS_P4_EMIT_X_EVENTS=0`, `LIDMAS_P4_EMIT_Z_EVENTS=1`) for robust replay across all decoders.

## Quick Start

```bash
./examples/paper_runs/paper_04/run_all.sh
```

By default, `run_all.sh` uses unified code-family analysis (`surface + gkp`) and writes the
canonical current-study outputs to:

- `examples/paper_runs/paper_04/results/03_analysis/`

## Script Map

- `01_generate_comparison_requests.sh`
  - Generates request NDJSON from repeated-round stabilizer circuits.
  - Uses PennyLane/Qiskit/Cirq when available, with per-framework fallback.
- `02_replay_decoder_matrix.sh`
  - Replays all request datasets through selected decoders via `--decoder_io_replay`.
  - Writes NDJSON responses and replay manifest.
- `03_analyze_comparison.sh`
  - Builds replay matrix summary CSV/Markdown.
  - Computes source-vs-reference deltas for each decoder.
  - Exports a two-panel figure (`avg flip count`, `warning rate`) in PNG/PDF.
- `04_extended_analysis.sh`
  - Runs pre-decoder request-equivalence audit.
  - Runs bootstrap confidence-interval analysis for decoder metrics and source deltas.
  - Writes an extended-analysis summary Markdown.
  - Optionally triggers scaling sweeps.
- `05_scaling_sweep.sh` (optional)
  - Re-runs steps 01-03 over multiple shot counts.
  - Writes timing + metric stability summaries and a scaling figure.
- `06_journal_plots.sh`
  - Builds journal-facing diagnostics from existing outputs:
    - source-vs-reference delta forest (95% CI)
    - decoder rank stability (bootstrap)
    - correction-set agreement matrix (mean Jaccard)
    - runtime log-log fit (if scaling table is available)
- `07_parametric_sweeps.sh` (optional)
  - Runs reproducible parameter sweeps:
    - noise-rate x rounds grid
    - distance sweep (`d=3,5,7` by default)
  - Exports heatmap and distance-trend figures.
- `08_code_family_comparison.sh` (optional)
  - Runs two isolated sub-workflows (typically `surface` and `gkp`) under `03_analysis/runs/`.
  - Produces the canonical unified current-study analysis in `results/03_analysis/`.
  - Computes within-family decoder comparisons and normalized cross-family trends.

## Main Outputs

- `results/01_generate_comparison_requests/table_request_manifest.csv`
- `results/01_generate_comparison_requests/summary_generation.json`
- `results/02_replay_decoder_matrix/replay_manifest.csv`
- `results/03_analysis/table_replay_matrix.csv` (family-aware, unified)
- `results/03_analysis/table_source_vs_lidmas.csv` (family-aware, unified)
- `results/03_analysis/table_family_decoder_summary.csv`
- `results/03_analysis/table_family_delta_effects.csv`
- `results/03_analysis/table_cross_family_normalized.csv`
- `results/03_analysis/figure_source_vs_lidmas.png` (family-aware tradeoff)
- `results/03_analysis/figure_family_tradeoff.png`
- `results/03_analysis/figure_family_delta_forest.png`
- `results/03_analysis/figure_cross_family_normalized_trends.png`
- `results/03_analysis/summary_code_family_comparison.md`
- `results/04_extended_analysis/table_request_equivalence.csv`
- `results/04_extended_analysis/table_bootstrap_metrics.csv`
- `results/04_extended_analysis/table_bootstrap_source_vs_reference.csv`
- `results/04_extended_analysis/figure_request_equivalence.png`
- `results/04_extended_analysis/figure_bootstrap_ci.png`
- `results/04_extended_analysis/summary_extended_analysis.md`
- `results/05_scaling_sweep/` (only if `LIDMAS_P4_ENABLE_SCALING=1`)
  - `sweep_manifest.csv`
  - `table_scaling_sweep.csv`
  - `table_scaling_sweep_by_decoder.csv`
  - `figure_scaling_sweep.png`
- `results/06_journal_plots/`
  - `table_delta_forest.csv`
  - `table_rank_stability.csv`
  - `table_correction_agreement.csv`
  - `table_runtime_scaling_fit.csv` (if scaling summary is available)
  - `figure_delta_forest.png`
  - `figure_rank_stability.png`
  - `figure_correction_agreement.png`
  - `figure_runtime_scaling_fit.png` (if scaling summary is available)
- `results/07_parametric_sweeps/` (only if `LIDMAS_P4_ENABLE_PARAM_SWEEPS=1`)
  - `table_parametric_runs.csv`
  - `table_noise_rounds_decoder.csv`
  - `table_distance_sweep_decoder.csv`
  - `figure_noise_rounds_heatmap.png`
  - `figure_distance_sweep.png`
- `results/03_analysis/runs/` (per-family internal run artifacts used to build unified outputs)

## Controls

- `LIDMAS_P4_SHOTS` (default: `2500`)
- `LIDMAS_P4_CODE_FAMILY` (default: `surface`; choices: `surface`, `gkp`)
- `LIDMAS_P4_DISTANCE` (default: `5`)
- `LIDMAS_P4_ROUNDS` (default: `4`)
- `LIDMAS_P4_N_QUBITS` (default: `40`, compatibility field; derived geometry is authoritative)
- `LIDMAS_P4_N_SYNDROME` (default: `20`, legacy field; ignored by geometry-based generator)
- `LIDMAS_P4_ERROR_RATE` (default: `0.08`)
- `LIDMAS_P4_SIGMA` (default: `0.18`)
- `LIDMAS_P4_SEED` (default: `20260409`)
- `LIDMAS_P4_EMIT_X_EVENTS` (default: `0`)
- `LIDMAS_P4_EMIT_Z_EVENTS` (default: `1`)
- `LIDMAS_P4_PENNYLANE_MODE`:
  - `auto` (default): use PennyLane if installed
  - `required`: fail if PennyLane is unavailable
  - `disabled`: fallback sampler
- `LIDMAS_P4_QISKIT_MODE`:
  - `auto` (default): use Qiskit if installed
  - `required`: fail if Qiskit is unavailable
  - `disabled`: fallback sampler
- `LIDMAS_P4_CIRQ_MODE`:
  - `auto` (default): use Cirq if installed
  - `required`: fail if Cirq is unavailable
  - `disabled`: fallback sampler
- `LIDMAS_P4_REFERENCE_DATASET` (default: `lidmas_reference`)
- `LIDMAS_P4_BOOTSTRAP` (default: `2000`)
- `LIDMAS_P4_BOOTSTRAP_SEED` (default: `20260409`)
- `LIDMAS_P4_ENABLE_SCALING` (default: `0`; set to `1` to run scaling sweeps)
- `LIDMAS_P4_SCALING_SHOTS` (default: `120,600,2400`)
- `LIDMAS_P4_RANK_BOOTSTRAP` (default: `4000`)
- `LIDMAS_P4_RANK_SEED` (default: `20260410`)
- `LIDMAS_P4_ENABLE_PARAM_SWEEPS` (default: `0`; set to `1` to run stage 07)
- `LIDMAS_P4_GRID_SHOTS` (default: `180`)
- `LIDMAS_P4_GRID_BASE_DISTANCE` (default: current `LIDMAS_P4_DISTANCE` or `5`)
- `LIDMAS_P4_GRID_NOISES` (default: `0.04,0.08,0.12`)
- `LIDMAS_P4_GRID_ROUNDS` (default: `2,4,6`)
- `LIDMAS_P4_GRID_DISTANCES` (default: `3,5,7`)
- `LIDMAS_P4_GRID_DISTANCE_ERROR_RATE` (default: current `LIDMAS_P4_ERROR_RATE` or `0.08`)
- `LIDMAS_P4_GRID_DISTANCE_ROUNDS` (default: current `LIDMAS_P4_ROUNDS` or `4`)
- `LIDMAS_P4_ENABLE_CODE_FAMILY` (default: `1`; unified current-study mode)
- `LIDMAS_P4_CODE_FAMILIES` (default: `surface,gkp`)
- `LIDMAS_P4_RESULTS_BASE` (optional root override for run outputs)
- `LIDMAS_DECODERS` (default: `mwpm,uf,bp,neural_mwpm`)
- `LIDMAS_NEURAL_MODEL` (optional path override)

## Example Commands

Strict three-framework run:

```bash
LIDMAS_P4_PENNYLANE_MODE=required \
LIDMAS_P4_QISKIT_MODE=required \
LIDMAS_P4_CIRQ_MODE=required \
./examples/paper_runs/paper_04/run_all.sh
```

Single-family GKP run:

```bash
LIDMAS_P4_CODE_FAMILY=gkp \
LIDMAS_DECODERS=mwpm,uf,bp \
./examples/paper_runs/paper_04/run_all.sh
```

Lightweight smoke run:

```bash
LIDMAS_P4_SHOTS=300 \
LIDMAS_P4_ROUNDS=3 \
LIDMAS_DECODERS=mwpm,uf,bp \
./examples/paper_runs/paper_04/run_all.sh
```

Extended run with scaling:

```bash
LIDMAS_P4_SHOTS=300 \
LIDMAS_P4_ROUNDS=3 \
LIDMAS_DECODERS=mwpm,uf,bp \
LIDMAS_P4_ENABLE_SCALING=1 \
LIDMAS_P4_SCALING_SHOTS=120,600,2400 \
./examples/paper_runs/paper_04/run_all.sh
```

Full journal plot pack (adds parameter sweeps):

```bash
LIDMAS_P4_SHOTS=300 \
LIDMAS_DECODERS=mwpm,uf,bp \
LIDMAS_P4_ENABLE_SCALING=1 \
LIDMAS_P4_ENABLE_PARAM_SWEEPS=1 \
LIDMAS_P4_SCALING_SHOTS=120,600,2400 \
LIDMAS_P4_GRID_SHOTS=180 \
./examples/paper_runs/paper_04/run_all.sh
```

Surface + GKP in-depth comparison (within-family + normalized cross-family trends):

```bash
LIDMAS_P4_SHOTS=240 \
LIDMAS_DECODERS=mwpm,uf,bp \
LIDMAS_P4_CODE_FAMILIES=surface,gkp \
./examples/paper_runs/paper_04/run_all.sh
```

Legacy single-family mode (disables unified family comparison):

```bash
LIDMAS_P4_ENABLE_CODE_FAMILY=0 \
LIDMAS_P4_CODE_FAMILY=surface \
LIDMAS_DECODERS=mwpm,uf,bp \
./examples/paper_runs/paper_04/run_all.sh
```
