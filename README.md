<p align="center">
  <img src="https://img.shields.io/badge/C%2B%2B-20-black?logo=c%2B%2B&logoColor=white" />
  <img src="https://img.shields.io/badge/build-CMake-black?logo=cmake&logoColor=white" />
  <img src="https://img.shields.io/github/v/tag/DennisWayo/lidmas_cpp?color=black&label=latest" />
  <img src="https://img.shields.io/github/license/DennisWayo/lidmas_cpp?color=black" />
  <img src="https://img.shields.io/badge/status-research--prototype-black" />
</p>

# LiDMaS+

**Logical Injection & Decoding Modeling System**

LiDMaS+ is a C++20 research codebase for classical LDPC belief propagation and CSS/surface-code-oriented extension layers.

## Current Version

**v0.6 — Surface MWPM decoder (boundary-aware) + threshold harness**

## What This Repository Includes

- Validated LDPC BP engine (sum-product + normalized min-sum)
- PEG-based LDPC construction and Tanner graph tooling
- Monte Carlo sweeps with BER/FER/iteration diagnostics
- CSS-ready decoding interfaces
- Planar surface-code infrastructure and dedicated surface runners
- Surface decoder plugin registry (`stub`, `mwpm`, `uf`, `neural_mwpm`)
- Surface threshold harness with OpenMP, confidence intervals, and threshold analysis

## Repository Layout

```text
include/
  core/          # Binary matrix primitives
  decoders/      # Belief propagation decoder
  graph/         # Tanner graph + diagnostics
  qec/           # CSS code/decoder + logical helpers
  surface/       # Surface lattice/code/syndrome/decoder
src/
  main.cpp       # LDPC sweep executable (lidmas)
  surface_main.cpp
```

## Build

```bash
mkdir -p build
cd build
cmake ..
make
```

OpenMP is optional. If unavailable, the project still builds and runs.

## Run: LDPC Sweep (Existing Path)

This is the existing validated sweep path and remains unchanged.

```bash
./lidmas
```

Optional flags:

```bash
./lidmas --bp=sum-product
./lidmas --bp=nms --alpha=0.8
./lidmas --quiet-iter-log
```

## Run: Surface Code (v0.4 Layer)

Distance-3 zero-noise sanity:

```bash
./lidmas_surface --d=3 --trials=200 --px=0 --pz=0
```

Small logical-failure sweep:

```bash
./lidmas_surface --d=3 --sweep --p_start=0.01 --p_end=0.10 --p_step=0.01 --trials=500
```

Typical output fields:

- `logicalX_fail_rate`
- `logicalZ_fail_rate`
- `logical_fail_rate`
- `avg_iters_x`
- `avg_iters_z`
- `commutation_ok` (checks `Hx * Hz^T == 0 mod 2`)

## Run: Surface Demo Modes (v0.6)

Use the main executable:

```bash
./lidmas --surface_demo=stub
./lidmas --surface_demo=mwpm
./lidmas --surface_demo=uf
./lidmas --surface_demo=neural_mwpm --neural_model=path/to/model.json
```

Printed fields:

- `defect_count_avg`
- `correction_weight_avg`
- `logical_fail_rate`

`uf` remains experimental.

## Run: Surface Threshold Harness (v0.6)

```bash
./lidmas --surface_threshold \
  --decoder=mwpm \
  --d=3,5,7 \
  --p_start=0.01 --p_end=0.15 --p_step=0.01 \
  --trials=2000 \
  --threads=8 \
  --seed=12345 \
  --out=surface_threshold.csv
```

Supported decoder options:

- `mwpm`
- `stub`
- `uf`
- `neural_mwpm` (with optional `--neural_model=<path>`)

Optional analysis flags:

- `--estimate_threshold` (pairwise crossing estimate)
- `--scaling_fit` (finite-size scaling fit for `p_c` and `nu`)
- `--auto_threshold` (compat alias for threshold estimate)

Adaptive-threshold flags:

- `--min_trials=<N>`
- `--max_trials=<N>`
- `--batch_trials=<N>`
- `--target_ci_halfwidth=<x>`
- `--target_rel_ci=<x>`
- `--monotonic_smooth`

CSV header:

```text
distance,p,trials,ler,ci_low,ci_high,defect_mean,weight_mean,decoder_fail_rate
```

Per-point console output includes Wilson 95% CI and decoder fail rate.

## Run: Smoke Checks

```bash
./lidmas --smoke
```

This runs a lightweight surface sanity check (`d=3`, `p=0`, `mwpm`) and expects `LER=0`.

## Run: Quantum CSS Demo (v0.5 Layer)

Use the LDPC binary with the optional QEC mode:

```bash
./lidmas --qec=css_demo
```

This runs a small CSS Monte Carlo demo and prints:

- `LER_total`
- `LER_X`
- `LER_Z`
- `avg_iter_X`
- `avg_iter_Z`

## Version History

### v0.6 — Surface MWPM decoder (boundary-aware) + threshold harness

Adds boundary-aware surface MWPM matching and a stabilized threshold harness while preserving validated LDPC and CSS paths.

- `MWPMDecoder` boundary matching for planar syndromes (defect-to-boundary support)
- Surface decoder plugins in `lidmas`: `--surface_demo=stub|mwpm|uf|neural_mwpm`
- Surface threshold harness with OpenMP support and `--threads`
- Wilson 95% confidence intervals and per-point `decoder_fail_rate`
- Optional threshold analysis: `--estimate_threshold`, `--scaling_fit`, `--auto_threshold`
- Failure capture to `surface_decoder_failure_dump.txt` on first decoder exception

### v0.5 — Quantum CSS Monte Carlo Engine

Adds a dedicated quantum noise and syndrome-simulation layer while preserving existing LDPC sweep behavior.

- `PauliChannel` for independent X/Z and depolarizing sampling
- Reusable CSS syndrome extraction helper
- Logical-failure helper utilities (`LogicalPair`, mod-2 overlap checks)
- `QuantumCSSSimulator` for dual BP decoding (X/Z), residual checks, and QEC metrics
- Optional CLI demo mode: `--qec=css_demo`

### v0.4 — Surface Code Infrastructure

Additive planar surface-code layer built on top of existing BP/CSS abstractions.

- `SurfaceLattice`, `SurfaceCode`, `SurfaceSyndrome`, `SurfaceDecoder`
- Independent X/Z decoding path using existing BP decoder
- Canonical logical-support overlap checks for logical-failure estimation
- Separate executable: `lidmas_surface`
- Existing LDPC sweep behavior preserved

### v0.3 — CSS-Ready BP Engine

Transition from classical LDPC decoding toward quantum error correction.

- Modular CSS code structure (X/Z parity separation)
- CSS syndrome handling layer
- Logical operator scaffolding
- Classical BP decoder reusable for X and Z decoding
- Clean architectural separation for future QEC extensions

This version prepares LiDMaS+ for quantum code integration (CSS, surface codes, and beyond).

### v0.2 — Validated LDPC Belief Propagation Engine

Research-grade LDPC BP implementation with validation diagnostics.

- PEG-generated regular LDPC codes (`n=1000`, `m=500`)
- Sum-product and normalized min-sum decoding
- Explicit all-zero codeword channel simulation
- Monotonic FER waterfall validation
- Parity satisfaction rate and max-iteration hit diagnostics
- OpenMP-parallel Monte Carlo sweeps
- Reproducible CMake build

Validated FER transition example:

- `p=0.06` → `FER=0.01`
- `p=0.07` → `FER=0.115`
- `p=0.08` → `FER=0.355`
- `p=0.09` → `FER=0.755`
- `p=0.10` → `FER=0.965`

This version marks the first experimentally validated decoding engine.

### v0.1 — Baseline Belief Propagation Prototype

Initial LDPC decoding framework.

- BinaryMatrix core implementation
- Tanner graph construction
- Classical min-sum belief propagation
- Basic Monte Carlo bit-flip (BSC) simulation
- Metrics: success rate and average iterations

This version established the foundational decoding architecture.
