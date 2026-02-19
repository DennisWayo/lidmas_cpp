<p align="center">
  <!-- Core Language & Platform -->
  <img src="https://img.shields.io/badge/C%2B%2B-20-black?logo=c%2B%2B&logoColor=white" />
  <img src="https://img.shields.io/badge/CMake-build-black?logo=cmake&logoColor=white" />
  <img src="https://img.shields.io/badge/macOS-Apple%20Silicon-black?logo=apple&logoColor=white" />
  <img src="https://img.shields.io/badge/Architecture-LDPC%20%7C%20CSS-black" />
  <img src="https://img.shields.io/badge/License-MIT-black" />
</p>

<p align="center">
  <img src="https://img.shields.io/github/v/release/DennisWayo/lidmas_cpp?color=black&label=version" />
  <img src="https://img.shields.io/badge/decoding-erasure--aware%20min--sum%20BP-black" />
  <img src="https://img.shields.io/badge/channel-bitflip%20%2B%20erasure-black" />
  <img src="https://img.shields.io/badge/simulation-Monte%20Carlo-black" />
  <img src="https://img.shields.io/badge/status-research--prototype-black" />
  <img src="https://img.shields.io/badge/core-binary%20matrix-black" />
  <img src="https://img.shields.io/badge/graph-Tanner%20graph-black" />
  <img src="https://img.shields.io/badge/metrics-success%20rate%20%7C%20avg%20iterations-black" />
</p>

# LiDMaS+

**Logical Injection & Decoding Modeling System**

LiDMaS+ is a C++20 research codebase for classical LDPC belief propagation and CSS/surface-code-oriented extension layers.

## What This Repository Includes

- Validated LDPC BP engine (sum-product + normalized min-sum)
- PEG-based LDPC construction and Tanner graph tooling
- Monte Carlo sweeps with BER/FER/iteration diagnostics
- CSS-ready decoding interfaces
- Planar surface-code infrastructure and a dedicated surface runner

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

## Version History

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
