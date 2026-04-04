# Examples and Workflows

LiDMaS+ includes reproducible experiment scripts in `examples/`.

## One-time setup

```bash
./examples/setup_env.sh
```

This creates `.venv/` and installs plotting dependencies.

Offline mode (CSV only):

```bash
LIDMAS_SKIP_PY_DEPS=1 ./examples/hybrid_threshold/run.sh
```

## Example index

- `hybrid_threshold/`: `LER vs sigma` in hybrid CV+GKP mode.
- `pauli_threshold/`: baseline discrete Pauli threshold (`LER vs p`).
- `cv_demo/`: minimal single-point CV+GKP check.
- `quick_smoke/`: quick install sanity check.
- `scaling_fit/`: crossing and finite-size scaling outputs.
- `adaptive_ci/`: adaptive trial stopping using CI targets.
- `reproducibility_seed/`: fixed-seed repeatability check.
- `decoder_comparison/`: compare decoders under same sweep.
- `failure_debug/`: stress run and failure-dump workflow.
- `plot_only/`: publication plotting from existing CSV files.

## Results location

All artifacts are written to:

- `examples/results/<example_name>/`

## Runtime guidance

- Full sweeps (`trials=2000`) can take minutes to hours.
- For fast checks, reduce trials:

```bash
LIDMAS_TRIALS=200 ./examples/hybrid_threshold/run.sh
```

## Minimal end-to-end run

```bash
bash examples/quick_smoke/run.sh
```
