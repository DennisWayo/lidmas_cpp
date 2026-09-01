#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "33_ingest_gkp_results")"
LOCAL_JSON="$(paper_results_dir "32_gkp_digitized_sampler")/local_gkp_digitized_results.json"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi
if [ ! -f "${LOCAL_JSON}" ]; then
  echo "Error: ${LOCAL_JSON} not found. Run digitized-GKP sampler first." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/ingest_gkp_digitized_results.py" \
  --out-dir "${OUT_DIR}" \
  --raw-json "${LOCAL_JSON}"

echo "paper_05 digitized-GKP step 33 complete: ${OUT_DIR}"
