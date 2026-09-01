#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "01_build_syndrome_circuits")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/build_repetition_syndrome.py" \
  --out-dir "${OUT_DIR}" \
  --n-data "${LIDMAS_P5_N_DATA:-5}" \
  --targets "${LIDMAS_P5_TARGETS:-all}"

echo "paper_05 step 01 complete: ${OUT_DIR}"
