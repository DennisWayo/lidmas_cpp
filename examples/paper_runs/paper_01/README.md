# Paper Runs

This directory contains paper-oriented workflows for the decoder-comparison manuscript:

**Decoder Performance in Hybrid CV-Discrete Surface-Code Threshold Estimation Using LiDMaS+**

These runs live under `examples/paper_runs/paper_01/` because they are intended to generate the exact figure and table inputs for the paper rather than general project demos.

## Workflow map

- `01_pauli_baseline.sh`
  - Figure 1 input
  - Fixed-distance Pauli decoder comparison at `d=5`
- `02_hybrid_baseline.sh`
  - Figure 2 input
  - Fixed-distance hybrid decoder comparison at `d=5`
- `03_hybrid_multidistance.sh`
  - Figure 3 input
  - Hybrid multi-distance comparison across `d=3,5,7`
- `04_pauli_threshold.sh`
  - Figure 4 / Table 2 input in Pauli mode
  - Decoder-specific threshold and scaling summaries
- `05_hybrid_threshold.sh`
  - Figure 4 / Table 2 input in hybrid mode
  - Decoder-specific practical crossing summaries
- `run_all.sh`
  - Runs the full paper workflow in sequence

## Output location

All generated artifacts are written under:

- `examples/paper_runs/paper_01/results/`

Each script creates its own subdirectory with:

- raw CSV outputs,
- merged CSV files where relevant,
- publication figures,
- summary tables in `.md` and `.csv`,
- threshold summary JSON/Markdown where supported by the binary.

## Default decoder policy

By default, the paper workflows run:

- `mwpm`
- `uf`

Neural-guided MWPM is **not** included by default (to keep runtime predictable), but the repository now ships a trained reference model at:

- `examples/decoder_comparison/trained_model.json`

To include neural runs, enable:

```bash
LIDMAS_INCLUDE_NEURAL=1
```

Optionally set a custom model path:

```bash
LIDMAS_NEURAL_MODEL=/path/to/model.json
```

## Recommended starting trial counts

For drafting and figure prototyping:

```bash
LIDMAS_TRIALS=500 ./examples/paper_runs/paper_01/01_pauli_baseline.sh
LIDMAS_TRIALS=500 ./examples/paper_runs/paper_01/02_hybrid_baseline.sh
```

For paper-quality runs:

- baseline figures: `3000-5000` trials per point
- threshold/scaling runs: `4000+` trials per point or adaptive refinement near crossings

## One-time setup

```bash
./examples/setup_env.sh
```

## Full run

```bash
./examples/paper_runs/paper_01/run_all.sh
```
