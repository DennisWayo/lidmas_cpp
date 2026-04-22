#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

usage() {
  cat <<'USAGE'
Usage:
  bash hardware_integration/xanadu/run_gkp_remote_ssh.sh [options]

Options:
  --remote <user@host>          SSH target (default: dela@macstudio)
  --remote-repo <path>          Remote lidmas_cpp repo path (default: ~/lidmas_cpp)
  --remote-input-root <path>    Remote root containing GKP .npz data (checked first)
                                (falls back to sample counts JSON if missing)
  --remote-python <cmd>         Remote Python executable (default: python3)
  --remote-counts-json <path>   Remote temp counts JSON (default: /tmp/lidmas_gkp_counts.json)
  --remote-requests <path>      Remote temp NDJSON output (default: /tmp/lidmas_decoder_requests_gkp_remote.ndjson)
  --mapping <path>              Mapping file relative to remote repo
                                (default: hardware_integration/xanadu/xanadu_gkp_mapping_example.json)
  --detectors <n>               Detector values parsed per outcome key (default: 3)
  --max-shots <n>               Max shots for converter (default: 0 = all)
  --progress-every <n>          Conversion progress interval (default: 10000)
  --local-out <path>            Local NDJSON destination
                                (default: examples/results/hardware_integration/decoder_requests_gkp_remote.ndjson)
  --run-id <uuid>               Run UUID for telemetry push to backend
  --backend-base-url <url>      Backend base URL, e.g. http://127.0.0.1:8080/api/v1
  --telemetry-url <url>         Direct telemetry endpoint URL (overrides backend-base-url/run-id)
  --max-telemetry-frames <n>    Max request rows to convert into telemetry (default: 1200; 0 = all)
  --http-timeout <seconds>      HTTP timeout for telemetry push (default: 15.0)
  --primary-decoder <name>      Primary correction decoder (default: mwpm)
  --shadow-decoders <csv>       Shadow decoders for exact evaluation (default: <none>)
  --neural-model <path>         Local neural model path (required for neural_mwpm replay)
  --expand-count-table          Expand counts into repeated shot rows (default: disabled)
  --skip-replay                 Skip local LiDMaS+ replay step
  --help                        Show this help

Example:
  bash hardware_integration/xanadu/run_gkp_remote_ssh.sh \
    --remote dela@macstudio \
    --remote-input-root examples/results/hardware_integration/downloads/gkp/full
USAGE
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Error: required command '${cmd}' not found." >&2
    exit 1
  fi
}

REMOTE="dela@macstudio"
REMOTE_REPO="~/lidmas_cpp"
REMOTE_INPUT_ROOT=""
REMOTE_PYTHON="python3"
REMOTE_COUNTS_JSON="/tmp/lidmas_gkp_counts.json"
REMOTE_REQUESTS="/tmp/lidmas_decoder_requests_gkp_remote.ndjson"
MAPPING_REL="hardware_integration/xanadu/xanadu_gkp_mapping_example.json"
REMOTE_FALLBACK_INPUT_REL="examples/results/hardware_integration/downloads/gkp/full"
REMOTE_FALLBACK_COUNTS_REL="hardware_integration/xanadu/xanadu_gkp_counts_example.json"
DETECTORS=3
MAX_SHOTS=0
PROGRESS_EVERY=10000
COUNT_TABLE_NO_EXPAND=1
RUN_REPLAY=1
LOCAL_OUT=""
RUN_ID=""
BACKEND_BASE_URL=""
TELEMETRY_URL=""
MAX_TELEMETRY_FRAMES=1200
HTTP_TIMEOUT=15.0
PRIMARY_DECODER="mwpm"
SHADOW_DECODERS=""
NEURAL_MODEL=""

while [ "${#}" -gt 0 ]; do
  case "$1" in
    --remote)
      REMOTE="${2:-}"
      shift 2
      ;;
    --remote-repo)
      REMOTE_REPO="${2:-}"
      shift 2
      ;;
    --remote-input-root)
      REMOTE_INPUT_ROOT="${2:-}"
      shift 2
      ;;
    --remote-python)
      REMOTE_PYTHON="${2:-}"
      shift 2
      ;;
    --remote-counts-json)
      REMOTE_COUNTS_JSON="${2:-}"
      shift 2
      ;;
    --remote-requests)
      REMOTE_REQUESTS="${2:-}"
      shift 2
      ;;
    --mapping)
      MAPPING_REL="${2:-}"
      shift 2
      ;;
    --detectors)
      DETECTORS="${2:-}"
      shift 2
      ;;
    --max-shots)
      MAX_SHOTS="${2:-}"
      shift 2
      ;;
    --progress-every)
      PROGRESS_EVERY="${2:-}"
      shift 2
      ;;
    --local-out)
      LOCAL_OUT="${2:-}"
      shift 2
      ;;
    --run-id)
      RUN_ID="${2:-}"
      shift 2
      ;;
    --backend-base-url)
      BACKEND_BASE_URL="${2:-}"
      shift 2
      ;;
    --telemetry-url)
      TELEMETRY_URL="${2:-}"
      shift 2
      ;;
    --max-telemetry-frames)
      MAX_TELEMETRY_FRAMES="${2:-}"
      shift 2
      ;;
    --http-timeout)
      HTTP_TIMEOUT="${2:-}"
      shift 2
      ;;
    --primary-decoder)
      PRIMARY_DECODER="${2:-}"
      shift 2
      ;;
    --shadow-decoders)
      SHADOW_DECODERS="${2:-}"
      shift 2
      ;;
    --neural-model)
      NEURAL_MODEL="${2:-}"
      shift 2
      ;;
    --expand-count-table)
      COUNT_TABLE_NO_EXPAND=0
      shift
      ;;
    --skip-replay)
      RUN_REPLAY=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option '$1'." >&2
      usage
      exit 1
      ;;
  esac
done

if [ -z "${REMOTE_INPUT_ROOT}" ]; then
  REMOTE_INPUT_ROOT="${REMOTE_FALLBACK_INPUT_REL}"
fi

case "${DETECTORS}" in
  ''|*[!0-9]*)
    echo "Error: --detectors must be a non-negative integer." >&2
    exit 1
    ;;
esac
if [ "${DETECTORS}" -le 0 ]; then
  echo "Error: --detectors must be > 0." >&2
  exit 1
fi

case "${MAX_SHOTS}" in
  ''|*[!0-9]*)
    echo "Error: --max-shots must be a non-negative integer." >&2
    exit 1
    ;;
esac

case "${PROGRESS_EVERY}" in
  ''|*[!0-9]*)
    echo "Error: --progress-every must be a non-negative integer." >&2
    exit 1
    ;;
esac

case "${MAX_TELEMETRY_FRAMES}" in
  ''|*[!0-9]*)
    echo "Error: --max-telemetry-frames must be a non-negative integer." >&2
    exit 1
    ;;
esac

PRIMARY_DECODER="$(echo "${PRIMARY_DECODER}" | tr -d '[:space:]')"
if [ -z "${PRIMARY_DECODER}" ]; then
  echo "Error: --primary-decoder cannot be empty." >&2
  exit 1
fi

normalize_decoder_csv() {
  local raw="$1"
  local joined=""
  local item
  IFS=',' read -r -a items <<< "${raw}"
  for item in "${items[@]}"; do
    item="$(echo "${item}" | tr -d '[:space:]')"
    if [ -z "${item}" ]; then
      continue
    fi
    if [ -z "${joined}" ]; then
      joined="${item}"
    else
      joined="${joined},${item}"
    fi
  done
  echo "${joined}"
}

SHADOW_DECODERS="$(normalize_decoder_csv "${SHADOW_DECODERS}")"

require_cmd ssh
require_cmd scp

RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration")"
if [ -z "${LOCAL_OUT}" ]; then
  LOCAL_OUT="${RESULT_DIR}/decoder_requests_gkp_remote.ndjson"
fi
LOCAL_OUT_DIR_RAW="$(dirname "${LOCAL_OUT}")"
mkdir -p "${LOCAL_OUT_DIR_RAW}"
LOCAL_OUT_DIR="$(cd "${LOCAL_OUT_DIR_RAW}" && pwd)"
LOCAL_OUT="${LOCAL_OUT_DIR}/$(basename "${LOCAL_OUT}")"

q_remote_repo="$(printf '%q' "${REMOTE_REPO}")"
q_remote_python="$(printf '%q' "${REMOTE_PYTHON}")"
q_remote_input_root="$(printf '%q' "${REMOTE_INPUT_ROOT}")"
q_remote_counts_json="$(printf '%q' "${REMOTE_COUNTS_JSON}")"
q_remote_requests="$(printf '%q' "${REMOTE_REQUESTS}")"
q_mapping_rel="$(printf '%q' "${MAPPING_REL}")"
q_remote_fallback_input_rel="$(printf '%q' "${REMOTE_FALLBACK_INPUT_REL}")"
q_remote_fallback_counts_rel="$(printf '%q' "${REMOTE_FALLBACK_COUNTS_REL}")"

remote_cmd=(
  "cd ${q_remote_repo}"
  "&& REMOTE_INPUT_ROOT=${q_remote_input_root}"
  "&& REMOTE_FALLBACK_INPUT_REL=${q_remote_fallback_input_rel}"
  "&& REMOTE_FALLBACK_COUNTS_REL=${q_remote_fallback_counts_rel}"
  "&& REMOTE_COUNTS_SOURCE=${q_remote_counts_json}"
  "&& if [ -d \"\${REMOTE_INPUT_ROOT}\" ]; then"
  "${q_remote_python} hardware_integration/xanadu/extract_gkp_counts_from_npz.py --input-root \"\${REMOTE_INPUT_ROOT}\" --out ${q_remote_counts_json} --detectors ${DETECTORS};"
  "elif [ -d \"\${REMOTE_FALLBACK_INPUT_REL}\" ]; then"
  "echo \"[remote] input root '\${REMOTE_INPUT_ROOT}' not found; falling back to '\${REMOTE_FALLBACK_INPUT_REL}'\";"
  "${q_remote_python} hardware_integration/xanadu/extract_gkp_counts_from_npz.py --input-root \"\${REMOTE_FALLBACK_INPUT_REL}\" --out ${q_remote_counts_json} --detectors ${DETECTORS};"
  "elif [ -f \"\${REMOTE_FALLBACK_COUNTS_REL}\" ]; then"
  "echo \"[remote] NPZ roots unavailable; falling back to count-table fixture '\${REMOTE_FALLBACK_COUNTS_REL}'\";"
  "REMOTE_COUNTS_SOURCE=\"\${REMOTE_FALLBACK_COUNTS_REL}\";"
  "else"
  "echo \"[remote] ERROR: input roots '\${REMOTE_INPUT_ROOT}' and '\${REMOTE_FALLBACK_INPUT_REL}' were not found, and fixture '\${REMOTE_FALLBACK_COUNTS_REL}' is missing in repo \$(pwd)\" >&2;"
  "exit 22;"
  "fi"
  "&& ${q_remote_python} hardware_integration/xanadu/convert_xanadu_job_to_decoder_io.py --source-format count_table_json --input \"\${REMOTE_COUNTS_SOURCE}\" --mapping ${q_mapping_rel} --out ${q_remote_requests} --max-shots ${MAX_SHOTS} --progress-every ${PROGRESS_EVERY} --sigma 0.10 --gate-error-rate 0.0004 --meas-error-rate 0.0006 --idle-error-rate 0.0002 --meta source=gkp_remote_ssh --meta split=remote_npz_counts"
)

if [ "${COUNT_TABLE_NO_EXPAND}" -eq 1 ]; then
  remote_cmd+=("--count-table-no-expand")
fi

echo "[remote] running extraction + conversion on ${REMOTE}"
ssh "${REMOTE}" "${remote_cmd[*]}"

mkdir -p "${LOCAL_OUT_DIR}"
echo "[copy] fetching ${REMOTE_REQUESTS} -> ${LOCAL_OUT}"
scp "${REMOTE}:${REMOTE_REQUESTS}" "${LOCAL_OUT}"
echo "[copy] wrote ${LOCAL_OUT}"

LOCAL_RESP=""
TELEMETRY_RESPONSES=()
if [ "${RUN_REPLAY}" -eq 1 ]; then
  base_req="$(basename "${LOCAL_OUT}")"
  base_resp="${base_req/requests/responses}"

  decoders=("${PRIMARY_DECODER}")
  if [ -n "${SHADOW_DECODERS}" ]; then
    IFS=',' read -r -a shadow_list <<< "${SHADOW_DECODERS}"
    for shadow_decoder in "${shadow_list[@]}"; do
      if [ -z "${shadow_decoder}" ] || [ "${shadow_decoder}" = "${PRIMARY_DECODER}" ]; then
        continue
      fi
      exists=0
      for existing in "${decoders[@]}"; do
        if [ "${existing}" = "${shadow_decoder}" ]; then
          exists=1
          break
        fi
      done
      if [ "${exists}" -eq 0 ]; then
        decoders+=("${shadow_decoder}")
      fi
    done
  fi

  echo "[replay] starting local decoder replay (primary=${PRIMARY_DECODER}, shadows=${SHADOW_DECODERS})"
  for decoder in "${decoders[@]}"; do
    decoder_suffix="$(printf '%s' "${decoder}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '_')"
    decoder_resp="${RESULT_DIR}/${base_resp%.ndjson}_${decoder_suffix}.ndjson"

    replay_args=(
      --decoder "${decoder}"
      "${LOCAL_OUT}"
      "${decoder_resp}"
    )
    if [ "${decoder}" = "neural_mwpm" ]; then
      if [ -n "${NEURAL_MODEL}" ]; then
        replay_args=(--decoder "${decoder}" --neural-model "${NEURAL_MODEL}" "${LOCAL_OUT}" "${decoder_resp}")
      else
        if [ "${decoder}" = "${PRIMARY_DECODER}" ]; then
          echo "[replay] error: primary decoder neural_mwpm requires --neural-model" >&2
          exit 1
        fi
        echo "[replay] warning: skipping neural_mwpm shadow replay because --neural-model is not set" >&2
        continue
      fi
    fi

    if bash "${SCRIPT_DIR}/replay.sh" "${replay_args[@]}"; then
      TELEMETRY_RESPONSES+=("${decoder_resp}")
      if [ "${decoder}" = "${PRIMARY_DECODER}" ]; then
        LOCAL_RESP="${decoder_resp}"
      fi
    else
      if [ "${decoder}" = "${PRIMARY_DECODER}" ]; then
        echo "[replay] error: primary decoder replay failed (${decoder}); aborting." >&2
        exit 1
      fi
      echo "[replay] warning: shadow decoder replay failed (${decoder}); continuing." >&2
    fi
  done
fi

if [ -n "${RUN_ID}" ]; then
  if [ -z "${TELEMETRY_URL}" ] && [ -z "${BACKEND_BASE_URL}" ]; then
    echo "[telemetry] run-id provided but no telemetry target (backend-base-url/telemetry-url); skipping push" >&2
  else
    PY_BIN="$(examples_python_bin "${REPO_ROOT}")" || {
      echo "Error: python3 not found; cannot push Xanadu telemetry." >&2
      exit 1
    }

    telemetry_args=(
      --input "${LOCAL_OUT}"
      --run-id "${RUN_ID}"
      --max-frames "${MAX_TELEMETRY_FRAMES}"
      --http-timeout "${HTTP_TIMEOUT}"
    )
    if [ -n "${TELEMETRY_URL}" ]; then
      telemetry_args+=(--telemetry-url "${TELEMETRY_URL}")
    else
      telemetry_args+=(--backend-base-url "${BACKEND_BASE_URL}")
    fi
    if [ "${#TELEMETRY_RESPONSES[@]}" -gt 0 ]; then
      for response_file in "${TELEMETRY_RESPONSES[@]}"; do
        telemetry_args+=(--responses "${response_file}")
      done
      telemetry_args+=(--primary-decoder "${PRIMARY_DECODER}")
      echo "[telemetry] pushing exact Xanadu telemetry for run ${RUN_ID}"
      "${PY_BIN}" "${SCRIPT_DIR}/push_decoder_requests_telemetry.py" "${telemetry_args[@]}"
    else
      echo "[telemetry] exact telemetry requires decoder responses; skipping push (rerun without --skip-replay)." >&2
    fi
  fi
fi

echo "[done] completed remote GKP replay preparation"
