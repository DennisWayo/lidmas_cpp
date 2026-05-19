# Script Source Catalog

This catalog documents where mathematically-relevant workflow computations are implemented.

## paper_04 Orchestration Scripts

| Script | Role | Main Inputs | Main Outputs | Mathematical Content |
|---|---|---|---|---|
| `examples/paper_runs/paper_04/01_generate_comparison_requests.sh` | build request streams | config/env + seed | `decoder_requests_*.ndjson` | repeated-round syndrome event generation |
| `examples/paper_runs/paper_04/02_replay_decoder_matrix.sh` | replay through decoders | request NDJSON + decoder list | `decoder_responses_*.ndjson`, replay manifest | decoder response sampling |
| `examples/paper_runs/paper_04/03_analyze_comparison.sh` | build comparison tables | request/responses | replay matrix + source-vs-reference tables/figures | delta metrics |
| `examples/paper_runs/paper_04/04_extended_analysis.sh` | deeper diagnostics | stage 01-03 artifacts | bootstrap/equivalence tables/figures | CI and divergence analysis |
| `examples/paper_runs/paper_04/05_scaling_sweep.sh` | multi-shot stability sweep | shot list + workflow | scaling manifest/tables/plots | runtime/statistical scaling behavior |
| `examples/paper_runs/paper_04/06_journal_plots.sh` | publication diagnostics | prior stage outputs | journal plot pack | rank, agreement, trend diagnostics |
| `examples/paper_runs/paper_04/07_parametric_sweeps.sh` | grid sweeps | noise/round/distance grids | heatmap + trend tables | parameter response surfaces |
| `examples/paper_runs/paper_04/08_code_family_comparison.sh` | surface vs gkp integration | per-family runs | unified family tables/plots | cross-family normalization/trends |

## paper_04 Python Analysis Sources

| Script | Key Statistics/Transform |
|---|---|
| `examples/paper_runs/paper_04/scripts/generate_comparison_requests.py` | geometry equations, repeated-round parity events |
| `examples/paper_runs/paper_04/scripts/analyze_pennylane_vs_lidmas.py` | source-reference deltas for flip/warning/event rates |
| `examples/paper_runs/paper_04/scripts/analyze_request_equivalence.py` | TV and JS divergence on request distributions |
| `examples/paper_runs/paper_04/scripts/analyze_bootstrap_ci.py` | bootstrap means and confidence intervals |
| `examples/paper_runs/paper_04/scripts/analyze_code_family_trends.py` | within/across family trend summaries |
| `examples/paper_runs/paper_04/scripts/analyze_journal_diagnostics.py` | journal-oriented diagnostic reductions |
| `examples/paper_runs/paper_04/scripts/summarize_scaling_sweep.py` | scaling summary aggregation |
| `examples/paper_runs/paper_04/scripts/summarize_parametric_sweeps.py` | parametric sweep summaries |

## Core Simulation/Decoder Sources

| Area | Files |
|---|---|
| Surface code + syndrome | `src/surface/SurfaceCode.cpp`, `src/surface/SurfaceSyndrome.cpp`, `src/surface/SurfacePipeline.cpp` |
| Decoders | `src/surface/MWPMDecoder.cpp`, `src/surface/UnionFindDecoder.cpp`, `src/decoders/BeliefPropagation.cpp` |
| Scaling/statistics | `src/surface/ScalingAnalysis.cpp`, `src/sim/MonteCarlo.cpp`, `src/sim/SurfaceThresholdRunner.cpp` |
| Replay path | `src/decoder_io/DecoderIOReplay.cpp`, `src/decoder_io/SurfaceDecoderAdapter.cpp` |

## Enterprise App Surface (Parity Visibility)

| Area | Notes |
|---|---|
| Runs/workflow panels | Private enterprise surface tracks the same workflow states and artifact manifests. |
| Integration/session API | Private service routes orchestrate the same replay scripts used in OSS workflows. |
| `paper_04` parity API | Private endpoints execute canonical `paper_04` scripts and compare manifest hashes. |

These files expose the same artifact-level outputs needed to compare CLI and App behavior.
