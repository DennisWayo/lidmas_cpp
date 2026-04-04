#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

PY_BIN="$(paper_python_bin)"
ANALYSIS_SCRIPT="${SCRIPT_DIR}/08_extended_analysis/run_extended_analysis.py"
OUT_DIR="${LIDMAS_EXTENDED_ANALYSIS_OUT_DIR:-$(paper_results_dir "08_extended_analysis")}"

ensure_examples_env "${REPO_ROOT}"
paper_prepare_plot_env

"${PY_BIN}" "${ANALYSIS_SCRIPT}" \
  --paper-root "${SCRIPT_DIR}" \
  --output-dir "${OUT_DIR}" \
  "$@"

echo "Extended analysis outputs written to: ${OUT_DIR}"
