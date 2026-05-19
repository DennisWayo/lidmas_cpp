# Software Architecture

## Layered Architecture

LiDMaS+ is organized as five layers:

1. **Code/geometry layer**
   - Surface/CSS/LDPC constructs and parity maps.
   - Main paths: `src/surface/*`, `src/qec/*`, `src/codes/*`.
2. **Noise/syndrome generation layer**
   - Pauli and CV-hybrid disturbances, syndrome extraction.
   - Main paths: `src/qec/PauliChannel*.cpp`, `src/gkp/*`, `src/hybrid/*`.
3. **Decoder layer**
   - MWPM, Union-Find, BP, neural-weighted variants.
   - Main paths: `src/surface/*Decoder*.cpp`, `src/decoders/*`, `src/models/*`.
4. **Statistical inference layer**
   - Monte Carlo aggregation, threshold/scaling analysis.
   - Main paths: `src/sim/*`, `src/surface/ScalingAnalysis*`.
5. **Workflow/product layer**
   - Reproducible scripts and figure/table generation.
   - Main paths: `examples/*`, especially `examples/paper_runs/paper_04/*`.

## Control Planes

- **CLI plane**: command-line execution through `lidmas` binary and shell workflows.
- **Enterprise app plane**: private application APIs and panels maintained outside this OSS release surface.

Design target: both planes should produce equivalent analysis artifacts for matched run configs.

## Runtime Topology (Enterprise App)

At high level:

- operator-facing panels request runs/sessions/manifests,
- service routes coordinate run execution and reporting,
- persisted artifacts are consumed back into analysis panels.

## Key Architectural Invariants

1. Decoder outputs are interpreted through stable schema contracts.
2. Metrics are calculated from persisted artifacts, not ephemeral UI state.
3. Workflow-level summaries are derived from run/session stores and remain filter-consistent.
