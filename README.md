<p align="center">
  <img src="https://img.shields.io/badge/C%2B%2B-20-black?logo=c%2B%2B&logoColor=white" />
  <img src="https://img.shields.io/badge/build-CMake-black?logo=cmake&logoColor=white" />
  <img src="https://img.shields.io/github/license/DennisWayo/lidmas_cpp?color=black" />
</p>

# LiDMaS+

**Logical Injection & Decoding Modeling System**

LiDMaS+ is a C++ research simulator software for quantum error-correction studies, focused on
surface-code threshold experiments under both discrete Pauli noise and hybrid
continuous-variable (CV)-discrete noise models.

## Statement of Need

Benchmarking decoder behavior and threshold trends requires reproducible, scriptable,
and inspectable simulation pipelines. LiDMaS+ provides:

- deterministic Monte Carlo runs with explicit seed control,
- multiple decoders under a common interface,
- confidence-interval-aware threshold outputs,
- publication-ready CSV and figure workflows in `examples/`.

This makes it suitable for method development, reproducibility appendices, and
comparative decoder studies.

## Core Capabilities

- Surface-code simulation with configurable code distance and trial counts.
- Decoder plugins: `mwpm`, `uf`, `neural_mwpm`.
- Noise modes:
  - `pauli`: sweep logical error rate versus physical Pauli error rate `p`.
  - `hybrid`: sweep logical error rate versus CV displacement scale `sigma` using GKP digitization.
- Optional threshold analysis tools (crossing estimates and scaling fits).
- Reproducible example suite under `examples/`.

## Requirements

- C++20 compiler
- CMake >= 3.16
- Optional: OpenMP for parallel threshold runs
- Optional (for plots): Python 3 with `matplotlib` and `pandas`

## Build

```bash
cmake -S . -B build
cmake --build build -j
```

Primary executable:

- `build/lidmas`

## Quick Start

Show CLI help:

```bash
./build/lidmas --help
```

Run deterministic smoke test:

```bash
./build/lidmas --smoke
```

Run a Pauli threshold sweep:

```bash
./build/lidmas --surface_threshold \
  --mode=pauli \
  --decoder=mwpm \
  --d=3,5,7 \
  --p_start=0.01 --p_end=0.15 --p_step=0.01 \
  --trials=2000 \
  --seed=1337 \
  --out=surface_threshold.csv
```

Run a hybrid CV sweep:

```bash
./build/lidmas --surface_threshold \
  --mode=hybrid \
  --decoder=mwpm \
  --d=3,5,7 \
  --sigma_start=0.05 --sigma_end=0.60 --sigma_step=0.05 \
  --trials=2000 \
  --seed=1337 \
  --out=surface_threshold.csv
```

Neural decoder note:

- `--decoder=neural_mwpm` requires `--neural_model=<path>`.

## Reproducible Examples

The `examples/` directory contains ready-to-run scripts for smoke checks,
Pauli/hybrid thresholds, scaling workflows, decoder comparison, and plotting.

Setup once:

```bash
./examples/setup_env.sh
```

Run a minimal end-to-end check:

```bash
bash examples/quick_smoke/run.sh
```

Generated artifacts are written to:

- `examples/results/<example_name>/`

## Output Schema

Threshold CSV output uses:

- `mode,distance,sigma,pauli_p,trials,ler,ci_low,ci_high,defect_mean,weight_mean,decoder_fail_rate,mwpm_weight_scale,mwpm_graph,timestamp`

## Validation

For quick validation in local or CI environments:

```bash
./build/lidmas --smoke
```

## Project Layout

```text
include/   # public headers and interfaces
src/       # simulator and decoder implementations
examples/  # reproducible runs and plotting scripts
```

## Release Notes

Detailed release notes and version-specific changes are tracked in Git tags and
GitHub Releases.

## Citation

If you use LiDMaS+ in academic work, cite the software release used for your
experiments (tag + commit hash). If a JOSS/arXiv record is available for your
release, cite that record directly.

Suggested software citation format:

```text
Wayo, D. (Year). LiDMaS+ (Version X.Y.Z) [Computer software].
https://github.com/DennisWayo/lidmas_cpp
```

## License

This project is released under the MIT License (see `LICENSE`).

## Contributing

Issues and pull requests are welcome. Please include:

- a clear problem statement,
- reproduction steps,
- expected versus observed behavior,
- and, where possible, a minimal test or script.
