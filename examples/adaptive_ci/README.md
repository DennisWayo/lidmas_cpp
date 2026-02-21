# Adaptive CI Example

Demonstrates adaptive stopping based on confidence interval targets.

The run uses:

- `--min_trials`
- `--max_trials`
- `--batch_trials`
- `--target_ci_halfwidth`

## Run

```bash
./examples/setup_env.sh
./examples/adaptive_ci/run.sh
```

## Outputs

- `examples/results/adaptive_ci/surface_threshold.csv`
- `examples/results/adaptive_ci/figure_adaptive_ci.png`
- `examples/results/adaptive_ci/figure_adaptive_ci.pdf`
- `examples/results/adaptive_ci/figure_adaptive_ci.svg`
