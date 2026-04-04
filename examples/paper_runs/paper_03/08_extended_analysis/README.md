# paper_03 Extended Analysis Module

This module generates a publication-ready figure/table pack for the LiDMaS+ hardware-to-decoder workflow paper, using existing replay outputs from `examples/paper_runs/paper_03/results/`.

## What It Produces

Output root (default):

- `examples/paper_runs/paper_03/results/08_extended_analysis/`

Subfolders:

- `figures/` (PNG + PDF, optional SVG, plus transparent PNG variants)
- `tables/` (all intermediate/figure tables as CSV)
- `logs/` (run log)

Main figure set:

- Figure A: decoder tradeoff scatter
- Figure B: residual burden vs intervention volume
- Figure C1/C2: sparsity-sensitivity curves
- Figure D: engine-swap consistency panel
- Figure F: provider comparison heatmap
- Figure G: decoder signature parallel-coordinates plot
- Figure H: control-ablation comparison (real vs synthetic)
- Figure I: workflow flowchart (hardware -> normalization -> replay -> decoders -> metrics -> figures)

Additional generated outputs:

- `tables/table_merged_metrics_extended.csv`
- `tables/table_decoder_stability.csv`
- `tables/table_figure_manifest.csv`
- `tables/table_artifact_hashes.csv`
- `extended_analysis_summary.md` (figure summaries + caption suggestions + placement recommendations)

## Inputs

The driver dynamically discovers inputs under:

- `results/**/replay_manifest.csv`
- `results/**/table_*quality.csv`

It parses paired request/response NDJSON from each discovered manifest and joins those metrics with available quality tables.

## Metric Definitions

Existing metrics (from replay + quality outputs):

- `request_lines`, `response_lines`, `response_ratio`
- `request_parse_errors`, `response_parse_errors`
- `warning_no_syndrome_rate`
- `avg_request_events`, `nonempty_request_event_rate`
- `avg_flip_count`, `nonempty_flip_rate`, `unique_flip_qubits`
- `decoder_name_mismatch_count`
- `syndrome_satisfied_rate`, `residual_nonzero_rate`
- `logical_fail_rate` (if available in quality tables)

Derived metrics in this module:

- `correction_efficiency_index = syndrome_satisfied_rate / (avg_flip_count + 1e-9)`
- `intervention_to_clearance_ratio = avg_flip_count / (syndrome_satisfied_rate + 1e-9)`
- `dataset_sparsity_index = 1 - nonempty_request_event_rate`
- `warning_invariance_score = 1 - normalized_abs(warning_no_syndrome_rate - dataset_mean_warning_rate)`
- `decoder_stability_score = 1 / (1 + cv(avg_flip_count) + cv(syndrome_satisfied_rate) + cv(residual_nonzero_rate))`

## Run

From repo root:

```bash
./examples/paper_runs/paper_03/08_run_extended_analysis.sh
```

With SVG output:

```bash
./examples/paper_runs/paper_03/08_run_extended_analysis.sh --export-svg
```

Tables/logs only:

```bash
./examples/paper_runs/paper_03/08_run_extended_analysis.sh --skip-figures
```

## Reproducibility Behavior

The driver exports SHA-256 hashes for generated artifacts (figures + tables) in:

- `tables/table_artifact_hashes.csv`

## Robustness

- Missing inputs are handled with warnings.
- Figures with insufficient data are skipped gracefully (pipeline continues).
- Dataset/provider/decoder discovery is dynamic from manifest + tables.
- Adding future providers (e.g., Quandela, Google) requires no code changes if they follow existing manifest/request-response conventions.
