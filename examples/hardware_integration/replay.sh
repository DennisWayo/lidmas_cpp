#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration")"
REQ="${RESULT_DIR}/decoder_requests.ndjson"
RESP="${RESULT_DIR}/decoder_responses.ndjson"
CFG="${REPO_ROOT}/schemas/surface_decoder_adapter_config.json"

if [ ! -f "${REQ}" ]; then
  bash "${SCRIPT_DIR}/run.sh"
fi

"${BIN}" --decoder_io_replay \
  --decoder_io_in="${REQ}" \
  --decoder_io_out="${RESP}" \
  --decoder_io_config="${CFG}" \
  --decoder_io_continue_on_error

echo "Wrote ${RESP}"
