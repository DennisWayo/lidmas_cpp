# Math-to-Code Traceability

This page maps canonical mathematical quantities to implementation loci.

## Equation-to-Implementation Map

| Mathematical Object | Representation | Primary Implementation Sources |
|---|---|---|
| \(s = He \bmod 2\) | syndrome parity map | `src/surface/SurfaceSyndrome.cpp`, `src/qec/CSSSyndrome.cpp`, `src/utils/SyndromeUtils.cpp` |
| \(n=2d(d-1)\), \(m_X=d^2\), \(m_Z=(d-1)^2\) | surface geometry cardinalities | `examples/paper_runs/paper_04/scripts/generate_comparison_requests.py` |
| MWPM objective \(\min \sum C_{uv}\) | defect matching cost minimization | `src/surface/MWPMDecoder.cpp`, `src/surface/MatchingProblem.cpp`, `src/surface/BlossomMWPM.cpp` |
| Union-Find cluster/peel steps | near-linear decoding heuristic | `src/surface/UnionFindDecoder.cpp`, `src/decoders/UnionFindDecoder.cpp` |
| BP message updates | probabilistic inference over Tanner graph | `src/decoders/BeliefPropagation.cpp`, `src/graph/TannerGraph.cpp` |
| \(\widehat{\mathrm{LER}}=k/N\) | trial aggregation | `src/sim/MonteCarlo.cpp`, `src/sim/SurfaceThresholdRunner.cpp` |
| Wilson/CI intervals | uncertainty quantification | `src/surface/ScalingAnalysis.cpp`, analysis scripts in `examples/` |
| TV/JS request distances | request-equivalence diagnostics | `examples/paper_runs/paper_04/scripts/analyze_request_equivalence.py` |
| Source-reference deltas | reproducible comparator metrics | `examples/paper_runs/paper_04/scripts/analyze_pennylane_vs_lidmas.py` |
| Bootstrap CIs | nonparametric uncertainty estimates | `examples/paper_runs/paper_04/scripts/analyze_bootstrap_ci.py` |

## Proof-Obligation-to-Test/Artifact Map

| Obligation | Artifact |
|---|---|
| O1 syndrome consistency | request/replay outputs and decoder diagnostics in `results/02_replay_decoder_matrix/` |
| O2 decoder output validity | `decoder_responses_*.ndjson` schema and parse checks |
| O3 deterministic replay | fixed-seed reruns + matching stage tables |
| O4 comparator correctness | `table_replay_matrix.csv` -> `table_source_vs_lidmas.csv` derivation |
| O5 CLI/App parity | `paper_04` manifest parity checks and run summaries in LiDMaS+ App |

## Notes

- This map is intentionally concrete: each math object points to one or more source files.
- As implementations evolve, update this page alongside code changes to keep trust intact.
