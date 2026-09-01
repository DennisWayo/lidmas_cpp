#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "04_ingest_results")"
LOCAL_JSON="$(paper_results_dir "02_local_simulation")/local_repetition_results.json"
IBM_JSON="$(paper_results_dir "03_ibm_runtime")/ibm_repetition_results.json"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

raw_args=()
if [ -f "${LOCAL_JSON}" ]; then
  raw_args+=(--raw-json "${LOCAL_JSON}")
fi
if [ -f "${IBM_JSON}" ]; then
  raw_args+=(--raw-json "${IBM_JSON}")
fi

if [ "${#raw_args[@]}" -eq 0 ]; then
  echo "Error: no raw paper_05 result JSON files found." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/ingest_repetition_results.py" \
  --out-dir "${OUT_DIR}" \
  "${raw_args[@]}"

echo "paper_05 step 04 complete: ${OUT_DIR}"
