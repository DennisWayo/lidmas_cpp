# System Overview

## Objective

LiDMaS+ provides reproducible logical-error studies for quantum error correction (QEC), with two primary goals:

1. Produce deterministic threshold and scaling artifacts from controlled experiment scripts.
2. Keep **open execution surfaces equivalent** at artifact level (same manifests/tables/plots when configuration is matched).

## Scope

In scope:

- Surface-code and hybrid CV/discrete replay pipelines.
- Decoder matrix comparison (`mwpm`, `uf`, `bp`, optional `neural_mwpm`).
- Paper workflow orchestration (`examples/paper_runs/*`), including `paper_04`.

Out of scope:

- Formal proof assistant verification.
- Hardware-specific physical calibration guarantees.

## Core Solution Surfaces

- **Simulation/decoding engine**: C++ modules under `src/`.
- **Experiment orchestration**: shell + Python in `examples/`.
- **Enterprise application stack**: maintained in a private track outside this OSS release surface.
- **Data products**: CSV/Markdown/PNG/PDF artifacts in `examples/results/` and `examples/paper_runs/*/results/`.

## Trust Model

The project increases trust through:

- deterministic seed controls,
- explicit manifest outputs,
- script-by-script traceability to mathematical quantities,
- parity checks between execution surfaces.
