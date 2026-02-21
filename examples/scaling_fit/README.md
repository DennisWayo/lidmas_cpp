# Scaling Fit Example

Publication-oriented finite-size scaling run in Pauli mode.

This script enables:

- `--estimate_threshold`
- `--scaling_fit`
- bootstrap confidence intervals

## Run

```bash
./examples/setup_env.sh
./examples/scaling_fit/run.sh
```

Optional:

```bash
LIDMAS_TRIALS=1200 LIDMAS_SCALING_BOOTSTRAP=100 ./examples/scaling_fit/run.sh
```

## Outputs

- `examples/results/scaling_fit/surface_threshold.csv`
- `examples/results/scaling_fit/scaling_report.md`
- `examples/results/scaling_fit/scaling_summary.json`
- `examples/results/scaling_fit/figure_scaling_fit.png`
- `examples/results/scaling_fit/figure_scaling_fit.pdf`
- `examples/results/scaling_fit/figure_scaling_fit.svg`
