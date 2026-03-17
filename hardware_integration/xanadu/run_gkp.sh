#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration")"

python3 "${SCRIPT_DIR}/convert_xanadu_job_to_decoder_io.py" \
  --source-format count_table_json \
  --input "${SCRIPT_DIR}/xanadu_gkp_counts_example.json" \
  --mapping "${SCRIPT_DIR}/xanadu_gkp_mapping_example.json" \
  --out "${RESULT_DIR}/decoder_requests_gkp.ndjson" \
  --max-shots 1000 \
  --sigma 0.10 \
  --gate-error-rate 0.0004 \
  --meas-error-rate 0.0006 \
  --idle-error-rate 0.0002 \
  --meta dataset=gkp

echo "Wrote ${RESULT_DIR}/decoder_requests_gkp.ndjson"
