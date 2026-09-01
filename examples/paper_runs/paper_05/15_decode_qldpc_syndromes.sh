#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_DIR="$(paper_results_dir "14_ingest_qldpc_results")"
OUT_DIR="$(paper_results_dir "15_decode_qldpc_syndromes")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/decode_css_ldpc_syndromes.py" \
  --in-dir "${IN_DIR}" \
  --out-dir "${OUT_DIR}"

echo "paper_05 qLDPC step 15 complete: ${OUT_DIR}"
