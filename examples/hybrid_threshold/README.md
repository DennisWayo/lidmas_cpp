# Hybrid Threshold Example

This run performs a **sigma sweep** for hybrid CV+discrete QEC:

- Surface-code distances: `d=3,5,7`
- Noise mode: `hybrid`
- Decoder: MWPM
- Sigma range: `0.05` to `0.60` in steps of `0.05`

In this mode, `sigma` is the standard deviation of Gaussian displacement noise (continuous-variable noise) before GKP digitization to Pauli flips.

## Run

From any directory:

```bash
./examples/setup_env.sh
./examples/hybrid_threshold/run.sh
```

Optional quick run:

```bash
LIDMAS_TRIALS=200 ./examples/hybrid_threshold/run.sh
```

## Outputs

- `examples/results/hybrid_threshold/surface_threshold.csv`
- `examples/results/hybrid_threshold/plot_threshold.py`
- `examples/results/hybrid_threshold/threshold_plot.png` (if Python plotting dependencies are available)
- `examples/results/hybrid_threshold/figure_hybrid_threshold.png` (600 dpi)
- `examples/results/hybrid_threshold/figure_hybrid_threshold.pdf`
- `examples/results/hybrid_threshold/figure_hybrid_threshold.svg`

The simulator also prints pairwise crossing estimates between code distances in the terminal summary.
