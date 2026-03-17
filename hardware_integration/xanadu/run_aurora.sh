#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration")"

python3 "${SCRIPT_DIR}/convert_xanadu_job_to_decoder_io.py" \
  --source-format aurora_switch_dir \
  --input "${SCRIPT_DIR}/aurora_batch_example" \
  --mapping "${SCRIPT_DIR}/xanadu_aurora_mapping_example.json" \
  --out "${RESULT_DIR}/decoder_requests_aurora.ndjson" \
  --aurora-binarize \
  --sigma 0.16 \
  --gate-error-rate 0.0007 \
  --meas-error-rate 0.0009 \
  --idle-error-rate 0.0003 \
  --meta dataset=aurora_decoder_demo

echo "Wrote ${RESULT_DIR}/decoder_requests_aurora.ndjson"
