#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "13_threading_fidelity")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

SOURCE_TIMINGS="${REPO_ROOT}/examples/paper_runs/paper_02/results/06_parallelization/timings.csv"
if [ ! -f "${SOURCE_TIMINGS}" ]; then
  echo "Source parallelization timings not found. Running 06_parallelization.sh first..."
  "${SCRIPT_DIR}/06_parallelization.sh"
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_threading_fidelity.py" \
  --timings "${SOURCE_TIMINGS}" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --out-csv "${RESULT_DIR}/table_threading_fidelity.csv" \
  --out-md "${RESULT_DIR}/table_threading_fidelity.md" \
  --out-prefix "${RESULT_DIR}/figure_threading_fidelity"

echo "Paper run 13 complete: ${RESULT_DIR}"
