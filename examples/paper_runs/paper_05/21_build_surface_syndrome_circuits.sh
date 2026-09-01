#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "21_build_surface_syndrome_circuits")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/build_surface_syndrome.py" \
  --out-dir "${OUT_DIR}" \
  --distance "${LIDMAS_P5_SURFACE_DISTANCE:-5}" \
  --targets "${LIDMAS_P5_SURFACE_TARGETS:-representative}"

echo "paper_05 surface step 21 complete: ${OUT_DIR}"
