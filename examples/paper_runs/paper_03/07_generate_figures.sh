#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

FIXTURE_CSV="$(paper_results_dir "03_decoder_matrix_analysis")/table_decoder_matrix.csv"
REAL_CSV="$(paper_results_dir "05_real_data_analysis")/table_real_data_decoder_matrix.csv"
OUT_DIR="$(paper_results_dir "07_figures")"
PY_BIN="$(paper_python_bin)"
PLOT_SCRIPT="${SCRIPT_DIR}/scripts/plot_decoder_matrices.py"

if [ ! -f "${FIXTURE_CSV}" ]; then
  "${SCRIPT_DIR}/03_analyze_decoder_matrix.sh"
fi

if [ ! -f "${REAL_CSV}" ]; then
  echo "Warning: real-data CSV missing; figure_real_* outputs may be skipped until run 05 is executed." >&2
fi

ensure_examples_env "${REPO_ROOT}"
paper_prepare_plot_env

"${PY_BIN}" "${PLOT_SCRIPT}" \
  --fixture-csv "${FIXTURE_CSV}" \
  --real-csv "${REAL_CSV}" \
  --out-dir "${OUT_DIR}"

echo "Wrote figures to ${OUT_DIR}"
