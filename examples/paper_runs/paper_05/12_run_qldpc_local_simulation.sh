#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "12_qldpc_local_simulation")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/run_local_css_ldpc_sampler.py" \
  --out-dir "${OUT_DIR}" \
  --targets "${LIDMAS_P5_QLDPC_TARGETS:-all}" \
  --shots "${LIDMAS_P5_QLDPC_SHOTS:-${LIDMAS_P5_SHOTS:-256}}" \
  --measurement-error-rate "${LIDMAS_P5_QLDPC_LOCAL_MEAS_ERROR:-0.02}" \
  --background-data-error-rate "${LIDMAS_P5_QLDPC_LOCAL_DATA_ERROR:-0.0}" \
  --seed "${LIDMAS_P5_QLDPC_SEED:-20260705}"

echo "paper_05 qLDPC step 12 complete: ${OUT_DIR}"
