#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

REPLAY_DIR="$(paper_results_dir "02_replay_decoder_matrix")"
ANALYSIS_DIR="$(paper_results_dir "03_analysis")"
EXT_DIR="$(paper_results_dir "04_extended_analysis")"
SCALING_DIR="$(paper_results_dir "05_scaling_sweep")"
OUT_DIR="$(paper_results_dir "06_journal_plots")"
mkdir -p "${OUT_DIR}"

if [ ! -f "${ANALYSIS_DIR}/table_replay_matrix.csv" ]; then
  "${SCRIPT_DIR}/03_analyze_comparison.sh"
fi
if [ ! -f "${EXT_DIR}/table_bootstrap_source_vs_reference.csv" ]; then
  "${SCRIPT_DIR}/04_extended_analysis.sh"
fi

PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

SCALING_CSV="${SCALING_DIR}/table_scaling_sweep.csv"
if [ ! -f "${SCALING_CSV}" ]; then
  SCALING_CSV=""
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_journal_diagnostics.py" \
  --matrix-csv "${ANALYSIS_DIR}/table_replay_matrix.csv" \
  --delta-csv "${EXT_DIR}/table_bootstrap_source_vs_reference.csv" \
  --replay-dir "${REPLAY_DIR}" \
  --out-dir "${OUT_DIR}" \
  --scaling-csv "${SCALING_CSV}" \
  --rank-bootstrap "${LIDMAS_P4_RANK_BOOTSTRAP:-4000}" \
  --seed "${LIDMAS_P4_RANK_SEED:-20260410}"

echo "paper_04 step 06 complete: ${OUT_DIR}"
