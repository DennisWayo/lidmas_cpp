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

## LiDMaS+

Logical Injection & Decoding Modeling System

Architecture-level quantum error correction simulator with erasure-aware belief propagation and Monte Carlo performance benchmarking.

## v0.4 Surface Code

LiDMaS+ now includes an additive planar surface-code layer (`include/surface`, `src/surface`) built on top of the existing BP/CSS abstractions.

Build:

```bash
mkdir -p build
cd build
cmake ..
make
```

Run surface decoder sanity (distance-3, zero noise):

```bash
./lidmas_surface --d=3 --trials=200 --px=0 --pz=0
```

Run a small logical-failure sweep:

```bash
./lidmas_surface --d=3 --sweep --p_start=0.01 --p_end=0.10 --p_step=0.01 --trials=500
```

## Version History

**v0.1** — Baseline Belief Propagation Prototype

Initial LDPC decoding framework.
- BinaryMatrix core implementation
- Tanner graph construction
- Classical min-sum belief propagation
- Basic Monte Carlo bit-flip (BSC) simulation
- Metrics: success rate and average iterations

This version established the foundational decoding architecture.


**v0.2** — Validated LDPC Belief Propagation Engine

Research-grade LDPC BP implementation with validation diagnostics.
- PEG-generated regular LDPC codes (n=1000, m=500)
- Sum-product and normalized min-sum decoding
- Explicit all-zero codeword channel simulation
- Monotonic FER waterfall validation
- Parity satisfaction rate and max-iteration hit diagnostics
- OpenMP-parallel Monte Carlo sweeps
- Reproducible CMake build

Validated FER transition example:
- p=0.06 → FER=0.01
- p=0.07 → FER=0.115
- p=0.08 → FER=0.355
- p=0.09 → FER=0.755
- p=0.10 → FER=0.965

This version marks the first experimentally validated decoding engine.


**v0.3** — CSS-Ready BP Engine

Transition from classical LDPC decoding toward quantum error correction.

- Modular CSS code structure (X/Z parity separation)
- CSS syndrome handling layer
- Logical operator scaffolding
- Classical BP decoder reusable for X and Z decoding
- Clean architectural separation for future QEC extensions

This version prepares LiDMaS+ for quantum code integration (CSS, surface codes, and beyond).
