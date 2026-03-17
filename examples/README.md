# Examples

Reproducible experiment entry points for LiDMaS+
## Setup (One Time)

```bash
./examples/setup_env.sh
```

This creates `.venv/` and installs plotting dependencies (`pandas`, `matplotlib`) without using system `pip`.

If you are offline and only need CSV outputs:

```bash
LIDMAS_SKIP_PY_DEPS=1 ./examples/hybrid_threshold/run.sh
```

## Example Index

- `hybrid_threshold/`: sigma sweep in hybrid CV+GKP mode (`LER vs sigma`).
- `pauli_threshold/`: baseline discrete Pauli threshold (`LER vs p`).
- `cv_demo/`: minimal single-point CV+GKP end-to-end check.
- `quick_smoke/`: short install sanity check (`--smoke` + mini threshold).
- `scaling_fit/`: crossing estimate + finite-size scaling fit outputs.
- `adaptive_ci/`: adaptive stopping with CI-based trial control.
- `reproducibility_seed/`: fixed-seed deterministic repeatability check.
- `decoder_comparison/`: same sweep across multiple decoders.
- `failure_debug/`: stress run and failure-dump capture workflow.
- `plot_only/`: publication-grade plotting from existing CSV files.
- `hardware_integration/`: convert Xanadu datasets (Aurora/QCA/GKP/job JSON) to LiDMaS+ decoder IO NDJSON.


## Central Results Folder

All generated CSV/plot/debug artifacts are written to:

- `examples/results/<example_name>/`

## Runtime Guidance

- Full sweeps (`trials=2000`) can take minutes to hours depending on CPU/threading.
- For fast checks, set lower trials:

```bash
LIDMAS_TRIALS=200 ./examples/hybrid_threshold/run.sh
```

## Notes

- Scripts can be launched from any directory.
- Scripts auto-detect `./lidmas` or `./build/lidmas`.
- Generated outputs are intentionally gitignored via `examples/.gitignore`.
