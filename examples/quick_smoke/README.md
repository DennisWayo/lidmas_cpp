# Quick Smoke Example

Fast installation sanity check for reproducibility pipelines.

It runs:

1. `./lidmas --smoke` (deterministic minimal smoke check)
2. A tiny Pauli mini-scan (`d=3`, `p=0.02..0.08`, `trials=80`, `seed=1337`)

## Run

```bash
./examples/setup_env.sh
./examples/quick_smoke/run.sh
```

## Outputs

- `examples/results/quick_smoke/surface_threshold.csv`
- `examples/results/quick_smoke/figure_quick_smoke.png`
- `examples/results/quick_smoke/figure_quick_smoke.pdf`
- `examples/results/quick_smoke/figure_quick_smoke.svg`
