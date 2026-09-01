#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "02_local_simulation")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/run_local_repetition_sampler.py" \
  --out-dir "${OUT_DIR}" \
  --n-data "${LIDMAS_P5_N_DATA:-5}" \
  --targets "${LIDMAS_P5_TARGETS:-all}" \
  --shots "${LIDMAS_P5_SHOTS:-256}" \
  --measurement-error-rate "${LIDMAS_P5_LOCAL_MEAS_ERROR:-0.02}" \
  --background-data-error-rate "${LIDMAS_P5_LOCAL_DATA_ERROR:-0.0}" \
  --seed "${LIDMAS_P5_SEED:-20260705}"

echo "paper_05 step 02 complete: ${OUT_DIR}"
