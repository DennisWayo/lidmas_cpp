# Architecture

LiDMaS+ is organized as a modular simulation stack with clear separation of concerns:

1. Lattice and code construction.
2. Noise generation (Pauli and hybrid CV-discrete).
3. Decoder plugins.
4. Threshold runner and statistical aggregation.
5. Plotting and reproducibility scripts.

## Decoder plugin model

Surface decoders are exposed via a shared interface and registered through plugin infrastructure:

- `mwpm`
- `uf`
- `neural_mwpm`

This enables controlled decoder swaps without changing the experiment harness.

## Noise modes

- `pauli`: discrete error-rate sweeps over `p`.
- `hybrid`: CV displacement sweeps over `sigma` with GKP digitization.

## Statistics layer

Threshold outputs include:

- logical error rate,
- confidence intervals,
- defect and correction-weight diagnostics.

The workflow supports reproducible Monte Carlo runs with deterministic trial seeding.

## Project layout

```text
include/   # public headers and interfaces
src/       # simulator and decoder implementations
examples/  # reproducible runs and plotting scripts
```

