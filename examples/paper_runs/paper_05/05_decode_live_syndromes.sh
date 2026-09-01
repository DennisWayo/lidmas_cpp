#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_DIR="$(paper_results_dir "04_ingest_results")"
OUT_DIR="$(paper_results_dir "05_decode_live_syndromes")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

if ! ls "${IN_DIR}"/decoder_requests_*.ndjson >/dev/null 2>&1; then
  "${SCRIPT_DIR}/04_ingest_results.sh"
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/decode_repetition_syndromes.py" \
  --in-dir "${IN_DIR}" \
  --out-dir "${OUT_DIR}"

echo "paper_05 step 05 complete: ${OUT_DIR}"
