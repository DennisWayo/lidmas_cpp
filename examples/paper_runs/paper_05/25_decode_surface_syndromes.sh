#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_DIR="$(paper_results_dir "24_ingest_surface_results")"
OUT_DIR="$(paper_results_dir "25_decode_surface_syndromes")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/decode_surface_syndromes.py" \
  --in-dir "${IN_DIR}" \
  --out-dir "${OUT_DIR}"

echo "paper_05 surface step 25 complete: ${OUT_DIR}"
