#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "31_build_gkp_digitized_model")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/build_gkp_digitized_model.py" \
  --out-dir "${OUT_DIR}" \
  --distance "${LIDMAS_P5_GKP_DISTANCE:-5}" \
  --targets "${LIDMAS_P5_GKP_TARGETS:-representative}" \
  --decision-width-scale "${LIDMAS_P5_GKP_DECISION_WIDTH_SCALE:-0.25}" \
  --injected-shift-scale "${LIDMAS_P5_GKP_INJECTED_SHIFT_SCALE:-0.56}"

echo "paper_05 digitized-GKP step 31 complete: ${OUT_DIR}"
