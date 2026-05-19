# Algorithm Specification

## End-to-End Pipeline

```text
Config + Seed
  -> Generate request streams
  -> Replay request streams through decoder matrix
  -> Aggregate per-decoder metrics
  -> Compare sources vs LiDMaS+ reference
  -> Bootstrap / equivalence diagnostics
  -> Export tables + figures + summaries
```

## paper_04 Canonical Flow

`examples/paper_runs/paper_04/run_all.sh` orchestrates:

1. `01_generate_comparison_requests.sh`
2. `02_replay_decoder_matrix.sh`
3. `03_analyze_comparison.sh`
4. `04_extended_analysis.sh`
5. `06_journal_plots.sh`
6. optional: `07_parametric_sweeps.sh`, `08_code_family_comparison.sh`, `05_scaling_sweep.sh`

## Deterministic Rules

1. Seed values are explicit (`LIDMAS_P4_SEED`, bootstrap seeds).
2. Output directories are deterministic by stage.
3. Metric tables are regenerated from persisted stage artifacts.

## Numerical Policy

- Means/rates computed in floating point from explicit counters.
- Confidence intervals from bootstrap or Wilson procedures.
- Output formatting fixed to stable decimal precision in CSV/Markdown emitters.
