# Failure Debug Example

Stress configuration intended to increase chances of decoder edge cases and show the failure-dump workflow.

The threshold runner writes the first decoder failure dump to:

- `surface_decoder_failure_dump.txt` (repo root)

This script copies it to:

- `examples/results/failure_debug/surface_decoder_failure_dump.txt` (if produced)

## Run

```bash
./examples/setup_env.sh
./examples/failure_debug/run.sh
```

## Outputs

- `examples/results/failure_debug/surface_threshold.csv`
- optional `examples/results/failure_debug/surface_decoder_failure_dump.txt`
- `examples/results/failure_debug/figure_failure_debug.png`
- `examples/results/failure_debug/figure_failure_debug.pdf`
- `examples/results/failure_debug/figure_failure_debug.svg`
