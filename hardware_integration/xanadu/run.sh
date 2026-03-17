#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration")"

python3 "${SCRIPT_DIR}/convert_xanadu_job_to_decoder_io.py" \
  --input "${SCRIPT_DIR}/xanadu_job_result_example.json" \
  --mapping "${SCRIPT_DIR}/xanadu_syndrome_mapping_example.json" \
  --out "${RESULT_DIR}/decoder_requests.ndjson" \
  --sigma 0.18 \
  --gate-error-rate 0.0007 \
  --meas-error-rate 0.0009 \
  --idle-error-rate 0.0003 \
  --meta calibration=2026-03-17

echo "Wrote ${RESULT_DIR}/decoder_requests.ndjson"
