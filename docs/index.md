# LiDMaS+

**Logical Injection & Decoding Modeling System**

LiDMaS+ is a quantum error-correction simulation stack focused on surface-code threshold experiments under:

- discrete Pauli noise, and
- hybrid continuous-variable (CV)-discrete noise via GKP digitization.

The project is designed for reproducible threshold workflows with deterministic seeding, pluggable decoders, and publication-ready CSV/plot artifacts.

## Documentation Roadmap

For technical review and trust-building, start with the **Technical Dossier**:

1. System overview and architecture
2. Formal problem definition
3. Mathematical foundations and exact methods
4. Proof obligations and algorithm specification
5. Math-to-code traceability and script source catalog
6. Validation and reproducibility protocol

Primary entry page: [Technical Dossier](technical/index.md).

## Install

### PyPI (recommended)

```bash
python -m pip install --upgrade lidmas
lidmas --help
```

Package name on PyPI is `lidmas`; software brand remains **LiDMaS+**.

### From source

```bash
cmake -S . -B build
cmake --build build -j
./build/lidmas --help
```

## Core capabilities

- Surface-code simulation with configurable code distance and trial counts.
- Decoder plugins: `mwpm`, `uf`, `neural_mwpm`.
- Noise modes:
  - `pauli`: sweep logical error rate versus physical Pauli error rate `p`.
  - `hybrid`: sweep logical error rate versus CV displacement scale `sigma`.
- Threshold analysis utilities (crossing estimates and scaling-fit support).
- Scripted example suite under `examples/`.

## Quick checks

```bash
lidmas --help
lidmas --smoke
```

For full commands, see [Getting Started](getting-started.md) and [CLI Reference](cli-reference.md).
For the derivation-first mathematical lecture flow, see [LiDMaS+ Math Notes](lidmas-math-lecture.md).
