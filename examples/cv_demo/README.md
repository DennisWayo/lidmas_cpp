# CV + GKP Demo Example

This is a minimal **single-configuration** hybrid run (not a sweep) intended to exercise:

- Gaussian displacement sampling
- GKP digitization to Pauli flips
- Surface-code syndrome extraction
- MWPM decoding

It uses `d=3` and `cv_sigma=0.2` for a quick reproducible check of the hybrid error-generation path.

## Run

From any directory:

```bash
./examples/setup_env.sh
./examples/cv_demo/run.sh
```

## Outputs

- `examples/results/cv_demo/surface_threshold.csv`
- `examples/results/cv_demo/plot_threshold.py`
- `examples/results/cv_demo/threshold_plot.png` (if plotting dependencies are available)
- `examples/results/cv_demo/figure_cv_demo.png` (600 dpi)
- `examples/results/cv_demo/figure_cv_demo.pdf`
- `examples/results/cv_demo/figure_cv_demo.svg`
