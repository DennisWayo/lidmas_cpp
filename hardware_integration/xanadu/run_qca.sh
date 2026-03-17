#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration")"

python3 "${SCRIPT_DIR}/convert_xanadu_job_to_decoder_io.py" \
  --source-format shot_matrix \
  --input "${SCRIPT_DIR}/xanadu_qca_samples_example.json" \
  --array-key samples \
  --mapping "${SCRIPT_DIR}/xanadu_qca_mapping_example.json" \
  --out "${RESULT_DIR}/decoder_requests_qca.ndjson" \
  --sigma 0.12 \
  --gate-error-rate 0.0005 \
  --meas-error-rate 0.0008 \
  --idle-error-rate 0.0002 \
  --meta dataset=qca

echo "Wrote ${RESULT_DIR}/decoder_requests_qca.ndjson"
