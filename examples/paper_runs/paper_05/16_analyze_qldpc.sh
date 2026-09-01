#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_CSV="$(paper_results_dir "15_decode_qldpc_syndromes")/decoded_shots.csv"
OUT_DIR="$(paper_results_dir "16_qldpc_analysis")"
MANUSCRIPT_DIR="${OUT_DIR}/manuscript_figures"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi
if [ ! -f "${IN_CSV}" ]; then
  echo "Error: ${IN_CSV} not found. Run qLDPC decode first." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_live_css_ldpc.py" \
  --decoded-csv "${IN_CSV}" \
  --out-dir "${OUT_DIR}" \
  --manuscript-dir "${MANUSCRIPT_DIR}"

echo "paper_05 qLDPC step 16 complete: ${OUT_DIR}"
