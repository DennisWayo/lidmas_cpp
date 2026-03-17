# paper_03 Workflow README

This directory contains the reproducible run scripts for `paper_03`.
Manuscript title:

- `A Practical Unified Hardware-to-Decoder Workflow for Hybrid Continuous-Variable and Discrete-Variable Quantum Error Correction in LiDMaS+`

Workflow location:

- `examples/paper_runs/paper_03/`

All outputs are written to:

- `examples/paper_runs/paper_03/results/<run_name>/`

## Scope

This workflow is hardware-integration focused. It generates decoder request NDJSON
from hardware-style fixtures, replays those requests through multiple decoders, and
builds paper-ready summary tables for response quality and correction behavior.

The first provider case study is:

- `hardware_integration/xanadu/`

## Prerequisites

1. Build the simulator binary:

```bash
cmake -S . -B build
cmake --build build -j
```

2. Ensure Python is available (`python3` or `.venv/bin/python`).

Notes:

- These scripts use only standard-library Python for analysis helpers.
- Optional real-data runs call `hardware_integration/xanadu/xandau_hardware_data.sh`,
  which may install `numpy` if requested.

## Quick Start

Run fixture-based workflow (`01` to `03`):

```bash
./examples/paper_runs/paper_03/run_all.sh
```

Run fixture + real-data slice workflow (`01` to `05`):

```bash
LIDMAS_RUN_REAL_DATA=1 ./examples/paper_runs/paper_03/run_all.sh
```

## Script Map

- `01_prepare_fixture_requests.sh`
  - Purpose: build decoder request NDJSON from local Xanadu fixture files.
  - Outputs: `decoder_requests*.ndjson`, `table_request_manifest.csv`
- `02_replay_decoder_matrix.sh`
  - Purpose: replay each request file across selected decoders.
  - Outputs: `decoder_responses_<dataset>_<decoder>.ndjson`, replay manifest
- `03_analyze_decoder_matrix.sh`
  - Purpose: summarize fixture replay matrix into paper-ready tables.
  - Outputs: `table_decoder_matrix.csv`, `table_decoder_matrix.md`
- `04_real_data_slice.sh`
  - Purpose: optional small-shot run on real public datasets (`aurora_min`, `qca_fig3b`).
  - Outputs: copied request slices + decoder response matrix + replay manifest
- `05_analyze_real_data_slice.sh`
  - Purpose: summarize optional real-data replay matrix.
  - Outputs: `table_real_data_decoder_matrix.csv`, `table_real_data_decoder_matrix.md`
- `06_sync_tables_to_tex.sh`
  - Purpose: sync LaTeX table rows in `paper_03.tex` from generated CSV summaries.
  - Inputs: `01_prepare_fixture_requests/table_request_manifest.csv`, `03_decoder_matrix_analysis/table_decoder_matrix.csv`, optional `05_real_data_analysis/table_real_data_decoder_matrix.csv`
  - Output: updated `paper_03.tex` table bodies for labels `tab:request_manifest_fixture`, `tab:decoder_matrix_fixture`, and `tab:decoder_matrix_real`
- `07_generate_figures.sh`
  - Purpose: generate publication-style decoder profile and warning-rate figures from fixture/real-data decoder matrix summaries.
  - Outputs: `results/07_figures/figure_fixture_avg_flip_profile.*`, `figure_fixture_avg_flip_heatmap.*`, `figure_real_avg_flip_profile.*`, `figure_fixture_warning_rate_bar.*`, `figure_real_warning_rate_bar.*`

## Manuscript Mapping (`paper_03.tex`)

Use the following mapping when drafting figures/tables in `paper_03.tex`.

- `01_prepare_fixture_requests.sh`
  - Supports: `\section{Xanadu Integration Case Study}` and `\subsection{Dataset Sources}`
  - Candidate table input: `results/01_prepare_fixture_requests/table_request_manifest.csv`
  - LaTeX label: `\label{tab:request_manifest_fixture}`
- `02_replay_decoder_matrix.sh`
  - Supports: `\section{Results}` and `\subsection{Conversion Correctness and Schema Compliance}`
  - Candidate raw data: `results/02_replay_decoder_matrix/decoder_responses_<dataset>_<decoder>.ndjson`
- `03_analyze_decoder_matrix.sh`
  - Supports: `\section{Results}`, `\subsection{Conversion Correctness and Schema Compliance}`, and `\subsection{Decoder Performance Across Hardware-Derived Inputs}`
  - Candidate paper tables:
    - `results/03_decoder_matrix_analysis/table_decoder_matrix.csv`
    - `results/03_decoder_matrix_analysis/table_decoder_matrix.md`
  - LaTeX label: `\label{tab:decoder_matrix_fixture}`
  - Candidate figure source for `\label{fig:warning_rate_profiles}`, `\label{fig:avg_flip_profiles}`, and `\label{fig:fixture_avg_flip_heatmap}` via `07_generate_figures.sh`
- `04_real_data_slice.sh` (optional)
  - Supports: `\section{Xanadu Integration Case Study}` and real public-data validation text
  - Candidate raw data: `results/04_real_data_slice/decoder_requests_*.ndjson` and `decoder_responses_*_*.ndjson`
- `05_analyze_real_data_slice.sh` (optional)
  - Supports: `\section{Results}` and `\subsection{Throughput, Scaling, and Reproducibility}` (real-data slice summary)
  - Candidate paper tables:
    - `results/05_real_data_analysis/table_real_data_decoder_matrix.csv`
    - `results/05_real_data_analysis/table_real_data_decoder_matrix.md`
  - LaTeX label: `\label{tab:decoder_matrix_real}`
  - Candidate figure source for `\label{fig:warning_rate_profiles}` and `\label{fig:avg_flip_profiles}` via `07_generate_figures.sh`

## Decoder Selection

Default decoder set:

- `mwpm`
- `uf`
- `bp`
- `neural_mwpm` (only if model exists)

Neural model default:

- `examples/decoder_comparison/trained_model.json`

Override decoder list:

```bash
LIDMAS_DECODERS=mwpm,uf,bp ./examples/paper_runs/paper_03/02_replay_decoder_matrix.sh
```

Override neural model path:

```bash
LIDMAS_NEURAL_MODEL=/path/to/model.json ./examples/paper_runs/paper_03/02_replay_decoder_matrix.sh
```

## Real-Data Slice Controls

Used by `04_real_data_slice.sh`:

- `LIDMAS_HW_DATASETS` (default: `aurora_min,qca_fig3b`)
- `LIDMAS_HW_MAX_SHOTS` (default: `5000`)
- `LIDMAS_HW_PROGRESS_EVERY` (default: `1000`)
- `LIDMAS_HW_FORCE_DOWNLOAD=1` to refresh cached downloads

Example:

```bash
LIDMAS_RUN_REAL_DATA=1 \
LIDMAS_HW_MAX_SHOTS=2000 \
LIDMAS_DECODERS=mwpm,uf \
./examples/paper_runs/paper_03/run_all.sh
```

## Release Context

This workflow targets LiDMaS+ `v1.2.0` and later hardware-integration layout:

- `hardware_integration/xanadu/`

## LaTeX Table Sync

After generating analysis CSVs, update `paper_03.tex` tables automatically:

```bash
./examples/paper_runs/paper_03/06_sync_tables_to_tex.sh
```

`run_all.sh` calls this sync step by default when `paper_03.tex` exists. Disable with:

```bash
LIDMAS_SYNC_PAPER_03_TEX=0 ./examples/paper_runs/paper_03/run_all.sh
```

## Figures

Generate/update figures explicitly:

```bash
./examples/paper_runs/paper_03/07_generate_figures.sh
```
