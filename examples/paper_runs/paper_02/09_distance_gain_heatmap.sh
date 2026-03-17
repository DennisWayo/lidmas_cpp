#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "09_distance_gain_heatmap")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

SOURCE_CSV="${REPO_ROOT}/examples/paper_runs/paper_02/results/03_gkp_multidistance/combined.csv"
if [ ! -f "${SOURCE_CSV}" ]; then
  echo "Source multi-distance results not found. Running 03_gkp_multidistance.sh first..."
  "${SCRIPT_DIR}/03_gkp_multidistance.sh"
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_distance_gain_heatmap.py" \
  --input "${SOURCE_CSV}" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --out-csv "${RESULT_DIR}/table_distance_gain.csv" \
  --out-md "${RESULT_DIR}/table_distance_gain.md" \
  --out-prefix "${RESULT_DIR}/figure_distance_gain_heatmap"

echo "Paper run 09 complete: ${RESULT_DIR}"
