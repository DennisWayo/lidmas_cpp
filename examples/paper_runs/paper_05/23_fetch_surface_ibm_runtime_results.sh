#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "23_surface_ibm_runtime")"
SUBMISSION_JSON="${OUT_DIR}/ibm_surface_submission.json"
RESULT_JSON="${OUT_DIR}/ibm_surface_results.json"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi
if [ ! -f "${SUBMISSION_JSON}" ]; then
  echo "Error: ${SUBMISSION_JSON} not found. Submit the IBM surface-code job first." >&2
  exit 1
fi

fetch_args=()
if [ "${LIDMAS_P5_SURFACE_IBM_STATUS_ONLY:-${LIDMAS_P5_IBM_STATUS_ONLY:-0}}" = "1" ]; then
  fetch_args+=(--status-only)
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/fetch_ibm_surface_results.py" \
  --submission-json "${SUBMISSION_JSON}" \
  --out-json "${RESULT_JSON}" \
  --result-timeout "${LIDMAS_P5_SURFACE_IBM_RESULT_TIMEOUT:-${LIDMAS_P5_IBM_RESULT_TIMEOUT:-300}}" \
  ${fetch_args[@]+"${fetch_args[@]}"}

if [ "${LIDMAS_P5_SURFACE_IBM_STATUS_ONLY:-${LIDMAS_P5_IBM_STATUS_ONLY:-0}}" = "1" ]; then
  echo "paper_05 surface IBM status check complete."
else
  echo "paper_05 surface IBM result fetch complete: ${RESULT_JSON}"
fi
