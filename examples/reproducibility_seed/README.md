# Reproducibility (Fixed Seed) Example

Runs the same hybrid sweep twice with identical seed and compares outputs.

To avoid false differences, the script removes the timestamp column and compares columns 1-13.

## Run

```bash
./examples/setup_env.sh
./examples/reproducibility_seed/run.sh
```

Optional:

```bash
LIDMAS_SEED=12345 LIDMAS_TRIALS=300 ./examples/reproducibility_seed/run.sh
```

## Outputs

- `examples/results/reproducibility_seed/run_a.csv`
- `examples/results/reproducibility_seed/run_b.csv`
- `examples/results/reproducibility_seed/reproducibility_report.txt`
- `examples/results/reproducibility_seed/reproducibility_diff.txt` (empty on pass)
- `examples/results/reproducibility_seed/figure_reproducibility_seed.png`
- `examples/results/reproducibility_seed/figure_reproducibility_seed.pdf`
- `examples/results/reproducibility_seed/figure_reproducibility_seed.svg`
