#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "36_gkp_figures")"
MANUSCRIPT_DIR="$(paper_results_dir "35_gkp_analysis")/manuscript_figures"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/render_gkp_digitized_figures.py" \
  --out-dir "${OUT_DIR}" \
  --manuscript-dir "${MANUSCRIPT_DIR}"

echo "paper_05 digitized-GKP step 36 complete: ${OUT_DIR}"
