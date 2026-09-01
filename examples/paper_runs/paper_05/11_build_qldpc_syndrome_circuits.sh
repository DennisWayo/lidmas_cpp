#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "11_build_qldpc_syndrome_circuits")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/build_css_ldpc_syndrome.py" \
  --out-dir "${OUT_DIR}" \
  --targets "${LIDMAS_P5_QLDPC_TARGETS:-all}"

echo "paper_05 qLDPC step 11 complete: ${OUT_DIR}"
