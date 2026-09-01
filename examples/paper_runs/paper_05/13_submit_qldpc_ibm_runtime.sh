#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "13_qldpc_ibm_runtime")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

backend_args=()
if [ -n "${LIDMAS_P5_QLDPC_IBM_BACKEND:-${LIDMAS_P5_IBM_BACKEND:-}}" ]; then
  backend_args+=(--backend "${LIDMAS_P5_QLDPC_IBM_BACKEND:-${LIDMAS_P5_IBM_BACKEND:-}}")
fi
if [ -n "${IBM_QUANTUM_INSTANCE:-}" ]; then
  backend_args+=(--instance "${IBM_QUANTUM_INSTANCE}")
fi
if [ "${LIDMAS_P5_QLDPC_IBM_WAIT:-${LIDMAS_P5_IBM_WAIT:-1}}" = "0" ]; then
  backend_args+=(--no-wait)
fi
if [ -n "${LIDMAS_P5_QLDPC_IBM_RESULT_TIMEOUT:-${LIDMAS_P5_IBM_RESULT_TIMEOUT:-}}" ]; then
  backend_args+=(--result-timeout "${LIDMAS_P5_QLDPC_IBM_RESULT_TIMEOUT:-${LIDMAS_P5_IBM_RESULT_TIMEOUT:-}}")
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/submit_ibm_css_ldpc_sampler.py" \
  --out-dir "${OUT_DIR}" \
  --targets "${LIDMAS_P5_QLDPC_TARGETS:-all}" \
  --shots "${LIDMAS_P5_QLDPC_IBM_SHOTS:-${LIDMAS_P5_QLDPC_SHOTS:-${LIDMAS_P5_SHOTS:-256}}}" \
  --optimization-level "${LIDMAS_P5_QLDPC_OPTIMIZATION_LEVEL:-${LIDMAS_P5_OPTIMIZATION_LEVEL:-1}}" \
  ${backend_args[@]+"${backend_args[@]}"}

echo "paper_05 qLDPC step 13 submit complete: ${OUT_DIR}"
