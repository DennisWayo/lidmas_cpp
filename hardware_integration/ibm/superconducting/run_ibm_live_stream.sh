#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

INSTALL_DEPS=0
ARGS=()
while [ "${#}" -gt 0 ]; do
  case "$1" in
    --install-deps)
      INSTALL_DEPS=1
      shift
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

PY_BIN="$(examples_python_bin "${REPO_ROOT}")" || {
  echo "Error: python3 not found." >&2
  exit 1
}

if [ "${INSTALL_DEPS}" -eq 1 ]; then
  echo "[deps] installing qiskit-ibm-runtime"
  "${PY_BIN}" -m pip install --upgrade qiskit-ibm-runtime
fi

RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration/ibm/superconducting")"
OUT_FILE="${RESULT_DIR}/ibm_live_stream.ndjson"

echo "[run] writing stream frames to ${OUT_FILE}"
"${PY_BIN}" "${SCRIPT_DIR}/ibm_live_noise_stream.py" \
  --out "${OUT_FILE}" \
  "${ARGS[@]}"

echo "[done] ibm live stream complete"
