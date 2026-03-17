#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

PY_BIN="$(paper_python_bin)"
SYNC_SCRIPT="${SCRIPT_DIR}/scripts/sync_tables_to_tex.py"
TEX_FILE="${REPO_ROOT}/paper_03.tex"
REQUEST_CSV="${REPO_ROOT}/examples/paper_runs/paper_03/results/01_prepare_fixture_requests/table_request_manifest.csv"
FIXTURE_CSV="${REPO_ROOT}/examples/paper_runs/paper_03/results/03_decoder_matrix_analysis/table_decoder_matrix.csv"
REAL_CSV="${REPO_ROOT}/examples/paper_runs/paper_03/results/05_real_data_analysis/table_real_data_decoder_matrix.csv"

if [ ! -f "${REQUEST_CSV}" ]; then
  "${SCRIPT_DIR}/01_prepare_fixture_requests.sh"
fi

if [ ! -f "${FIXTURE_CSV}" ]; then
  "${SCRIPT_DIR}/03_analyze_decoder_matrix.sh"
fi

# Real-data CSV is optional; if missing, sync script writes a not_run row.
"${PY_BIN}" "${SYNC_SCRIPT}" \
  --tex "${TEX_FILE}" \
  --request-csv "${REQUEST_CSV}" \
  --fixture-csv "${FIXTURE_CSV}" \
  --real-csv "${REAL_CSV}"

echo "Synced LaTeX tables in ${TEX_FILE}"
