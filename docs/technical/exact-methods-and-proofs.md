# Exact Methods and Proof Obligations

LiDMaS+ uses exact or explicitly-defined computational procedures at each stage. This section documents method-level proof obligations for engineering trust.

## Method Classes

1. **Syndrome construction**
   - Exact parity evaluation over defined check supports.
2. **Decoder optimization/inference**
   - MWPM objective minimization on constructed defect graphs.
   - Union-Find + peeling graph procedure.
   - BP message-passing approximations with explicit update rules.
3. **Statistical inference**
   - Closed-form estimators (means/rates/Wilson) and bootstrap CIs.
4. **Cross-source comparators**
   - Explicit delta metrics, TV distance, and Jensen-Shannon divergence.

## Proof Obligations (Engineering Form)

| Obligation | Statement |
|---|---|
| O1: Syndrome consistency | Generated/corrected syndromes must satisfy parity relations in the selected code geometry. |
| O2: Decoder output validity | Corrections must be schema-valid and auditable per request line. |
| O3: Deterministic replay | Fixed seeds/configs produce equivalent artifacts on rerun. |
| O4: Comparator correctness | Source-vs-reference deltas are computed directly from exported tables, not ad hoc UI transforms. |
| O5: Surface parity | CLI and App use equivalent workflow semantics for `paper_04` parity checks. |

## Theorem-Style Claims (Current Scope)

### Claim A: Reproducible Metric Extraction

Given fixed artifacts and deterministic parsing rules, replay metrics are deterministic functions of input NDJSON.

Evidence paths:

- `examples/paper_runs/paper_04/scripts/analyze_pennylane_vs_lidmas.py`
- `examples/paper_runs/paper_04/scripts/analyze_bootstrap_ci.py`

### Claim B: Request-Set Equivalence Distances Are Well-Defined

TV and JS statistics are computed from empirical PMFs over extracted event counts.

Evidence path:

- `examples/paper_runs/paper_04/scripts/analyze_request_equivalence.py`

### Claim C: Geometry-Constrained Generator Consistency

Request generation uses explicit distance-driven formulas \(n, m_X, m_Z\) and support maps.

Evidence path:

- `examples/paper_runs/paper_04/scripts/generate_comparison_requests.py`

## Boundary

These are implementation-level correctness obligations, not machine-checked formal proofs. The trust mechanism is transparent computation + artifact traceability.
