#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_DIR="$(paper_results_dir "05_decode_live_syndromes")"
OUT_DIR="$(paper_results_dir "06_analysis")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

if [ ! -f "${IN_DIR}/decoded_shots.csv" ]; then
  "${SCRIPT_DIR}/05_decode_live_syndromes.sh"
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_live_repetition.py" \
  --decoded-csv "${IN_DIR}/decoded_shots.csv" \
  --out-dir "${OUT_DIR}" \
  --manuscript-dir "${OUT_DIR}/manuscript_figures"

echo "paper_05 step 06 complete: ${OUT_DIR}"
