# Results, Risks, and Limits

## Result Surfaces Produced by Current Workflows

- Decoder replay matrix summaries.
- Source-vs-reference deltas.
- Bootstrap confidence intervals.
- Request-equivalence divergence metrics.
- Scaling and parametric trend plots (optional stages).

## Trust Risks to Monitor

1. **Dependency drift** across PennyLane/Qiskit/Cirq versions.
2. **Schema drift** in request/response NDJSON payloads.
3. **Config mismatch** between CLI and App runs.
4. **Silent fallback behavior** when optional dependencies are absent.
5. **Over-interpretation** of finite-shot differences.

## Mitigations

- pin and record environment versions,
- keep schema checks in replay/analysis stages,
- persist run manifests and seed/config snapshots,
- compare against LiDMaS+ reference dataset per decoder.

## Current Boundaries

- Engineering-grade reproducibility is provided.
- Formal proof-assistant verification is not yet integrated.
- Hardware calibration validity is external to this repository.

## Open Problems

1. Formalizing proof obligations into machine-checkable contracts.
2. Stronger automated parity checks across CLI and App routes.
3. Wider stress tests for cross-family normalization assumptions.
