# LiDMaS+

**Logical Injection & Decoding Modeling System**

LiDMaS+ is a C++ research simulator for quantum error-correction studies, focused on surface-code threshold experiments under:

- discrete Pauli noise, and
- hybrid continuous-variable (CV)-discrete noise via GKP digitization.

The project is designed for reproducible threshold workflows with deterministic seeding, pluggable decoders, and publication-ready CSV/plot artifacts.

## Core capabilities

- Surface-code simulation with configurable code distance and trial counts.
- Decoder plugins: `mwpm`, `uf`, `neural_mwpm`.
- Noise modes:
  - `pauli`: sweep logical error rate versus physical Pauli error rate `p`.
  - `hybrid`: sweep logical error rate versus CV displacement scale `sigma`.
- Threshold analysis utilities (crossing estimates and scaling-fit support).
- Scripted example suite under `examples/`.

## Quick start

Build:

```bash
cmake -S . -B build
cmake --build build -j
```

Run:

```bash
./build/lidmas --help
./build/lidmas --smoke
```

For full commands, see [Getting Started](getting-started.md) and [CLI Reference](cli-reference.md).

