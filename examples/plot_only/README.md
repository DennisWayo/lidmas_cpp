# Plot-Only Example

Generate publication-quality figures (PNG/PDF/SVG) from an existing threshold CSV.

## Setup

```bash
./examples/setup_env.sh
```

## Usage

```bash
./examples/plot_only/run.sh <csv_path> <output_prefix> [mode] [x_col] [group_col] [title]
```

Example:

```bash
./examples/plot_only/run.sh \
  examples/results/hybrid_threshold/surface_threshold.csv \
  examples/results/hybrid_threshold/figure_hybrid_threshold \
  hybrid sigma distance "Hybrid CV Threshold (MWPM)"
```

Outputs:

- `<output_prefix>.png` (600 dpi)
- `<output_prefix>.pdf`
- `<output_prefix>.svg`
