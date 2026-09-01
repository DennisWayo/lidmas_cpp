#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "32_gkp_digitized_sampler")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/run_local_gkp_digitized_sampler.py" \
  --out-dir "${OUT_DIR}" \
  --distance "${LIDMAS_P5_GKP_DISTANCE:-5}" \
  --targets "${LIDMAS_P5_GKP_TARGETS:-representative}" \
  --shots "${LIDMAS_P5_GKP_SHOTS:-${LIDMAS_P5_SHOTS:-4096}}" \
  --rounds "${LIDMAS_P5_GKP_ROUNDS:-3}" \
  --sigma-shift-scale "${LIDMAS_P5_GKP_SIGMA_SHIFT_SCALE:-0.015}" \
  --measurement-error-rate "${LIDMAS_P5_GKP_MEAS_ERROR:-0.01}" \
  --jump-prob "${LIDMAS_P5_GKP_JUMP_PROB:-0.001}" \
  --jump-scale "${LIDMAS_P5_GKP_JUMP_SCALE:-0.5}" \
  --decision-width-scale "${LIDMAS_P5_GKP_DECISION_WIDTH_SCALE:-0.25}" \
  --injected-shift-scale "${LIDMAS_P5_GKP_INJECTED_SHIFT_SCALE:-0.56}" \
  --seed "${LIDMAS_P5_GKP_SEED:-20260706}" \
  --pennylane-mode "${LIDMAS_P5_GKP_PENNYLANE_MODE:-required}" \
  --pennylane-squeeze-r "${LIDMAS_P5_GKP_PENNYLANE_SQUEEZE_R:-2.0}" \
  --pennylane-noise-scale "${LIDMAS_P5_GKP_PENNYLANE_NOISE_SCALE:-1.0}"

echo "paper_05 digitized-GKP step 32 complete: ${OUT_DIR}"
