#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration")"

usage() {
  cat <<'USAGE'
Usage:
  bash hardware_integration/xanadu/replay.sh [options] [request_ndjson] [response_ndjson]

Options:
  --decoder <name>        Decoder plugin name (default: mwpm)
  --neural-model <path>   Neural model path (required when decoder=neural_mwpm)
  --help                  Show this help
USAGE
}

DECODER="mwpm"
NEURAL_MODEL=""
POSITIONAL=()

while [ "${#}" -gt 0 ]; do
  case "$1" in
    --decoder)
      DECODER="${2:-}"
      shift 2
      ;;
    --neural-model)
      NEURAL_MODEL="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

if [ "${#POSITIONAL[@]}" -ge 1 ]; then
  REQ="${POSITIONAL[0]}"
else
  REQ="${RESULT_DIR}/decoder_requests.ndjson"
fi
if [ "${#POSITIONAL[@]}" -ge 2 ]; then
  RESP="${POSITIONAL[1]}"
else
  BASE_REQ="$(basename "${REQ}")"
  BASE_RESP="${BASE_REQ/requests/responses}"
  RESP="${RESULT_DIR}/${BASE_RESP}"
fi

BASE_CFG="${REPO_ROOT}/schemas/surface_decoder_adapter_config.json"
TMP_DECODER_TAG="$(printf '%s' "${DECODER}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '_')"
TMP_CFG_BASE="$(mktemp "${TMPDIR:-/tmp}/lidmas_surface_decoder_cfg.${TMP_DECODER_TAG}.XXXXXXXX")"
TMP_CFG="${TMP_CFG_BASE}.json"
mv "${TMP_CFG_BASE}" "${TMP_CFG}"

python3 - <<PY "${BASE_CFG}" "${TMP_CFG}" "${DECODER}" "${NEURAL_MODEL}"
import json
import sys

base_cfg, out_cfg, decoder, neural_model = sys.argv[1:]
with open(base_cfg, "r", encoding="utf-8") as handle:
    cfg = json.load(handle)

decoder = decoder.strip()
if not decoder:
    raise SystemExit("decoder cannot be empty")
cfg["decoder_name"] = decoder

if decoder == "neural_mwpm":
    model = neural_model.strip()
    if not model:
        raise SystemExit("decoder neural_mwpm requires --neural-model <path>")
    cfg["neural_model_path"] = model
    cfg["neural_weights_path"] = model
else:
    cfg["neural_model_path"] = ""
    cfg["neural_weights_path"] = ""

with open(out_cfg, "w", encoding="utf-8") as handle:
    json.dump(cfg, handle, indent=2)
    handle.write("\n")
PY

trap 'rm -f "${TMP_CFG}"' EXIT

if [ ! -f "${REQ}" ]; then
  bash "${SCRIPT_DIR}/run.sh"
fi

"${BIN}" --decoder_io_replay \
  --decoder_io_in="${REQ}" \
  --decoder_io_out="${RESP}" \
  --decoder_io_config="${TMP_CFG}" \
  --decoder_io_continue_on_error

echo "Wrote ${RESP} (decoder=${DECODER})"
