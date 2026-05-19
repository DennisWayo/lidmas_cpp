#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

source "${REPO_ROOT}/examples/common.sh"
source "${REPO_ROOT}/examples/paper_runs/paper_04/common.sh"

usage() {
  cat <<'USAGE'
Usage:
  bash hardware_integration/simulators/run_framework_replay.sh [options]

Options:
  --framework <pennylane|qiskit|cirq>   Simulator framework (required).
  --run-id <uuid>                       Run UUID for backend telemetry push (required).
  --backend-base-url <url>              Backend API base URL, e.g. http://127.0.0.1:8080/api/v1
  --telemetry-url <url>                 Direct telemetry endpoint URL override.
  --decoders <csv>                      Decoder list (default: mwpm,uf,bp).
  --code-family <surface|gkp>           Code family (default: surface).
  --shots <n>                           Request rows per dataset (default: 240).
  --distance <odd n>                    Code distance (default: 5).
  --rounds <n>                          Repeated rounds per shot (default: 4).
  --error-rate <f>                      Error rate (default: 0.08).
  --sigma <f>                           Sigma metadata value (default: 0.18).
  --seed <n>                            RNG seed (default: 20260515).
  --emit-x-events <0|1>                 Emit X events (default: 0).
  --emit-z-events <0|1>                 Emit Z events (default: 1).
  --neural-model <path>                 Neural model override for neural_mwpm.
  --circuit-name <text>                 Optional circuit label for metadata.
  --circuit-qubits <n>                  Circuit qubit count (required with --circuit-gate-plan).
  --circuit-qasm <text>                 Optional OpenQASM payload for metadata.
  --circuit-hardware-target <name>      Hardware target: superconducting|trapped_ion|photonic.
  --circuit-detector-model <name>       Photonic detector model: threshold|pnr_approx.
  --circuit-noise-config <json>         Optional noise profile JSON from circuit designer.
  --circuit-compile-artifact <json>     Optional deterministic compile artifact JSON.
  --circuit-calibration-snapshot <id>   Optional vendor calibration snapshot id.
  --circuit-calibration-catalog <path>  Optional vendor calibration catalog JSON path.
  --circuit-gate-plan <json>            Circuit gate plan JSON array for custom request generation.
  --max-telemetry-frames <n>            Max frames sent to telemetry (default: 1200; 0=all).
  --http-timeout <seconds>              Telemetry HTTP timeout (default: 20).
  --help                                Show this help.
USAGE
}

FRAMEWORK=""
RUN_ID=""
BACKEND_BASE_URL=""
TELEMETRY_URL=""
DECODER_CSV="mwpm,uf,bp"
CODE_FAMILY="surface"
SHOTS=240
DISTANCE=5
ROUNDS=4
ERROR_RATE=0.08
SIGMA=0.18
SEED=20260515
EMIT_X_EVENTS=0
EMIT_Z_EVENTS=1
NEURAL_MODEL=""
CIRCUIT_NAME=""
CIRCUIT_QUBITS=""
CIRCUIT_QASM=""
CIRCUIT_HARDWARE_TARGET=""
CIRCUIT_DETECTOR_MODEL=""
CIRCUIT_NOISE_CONFIG=""
CIRCUIT_COMPILE_ARTIFACT=""
CIRCUIT_CALIBRATION_SNAPSHOT=""
CIRCUIT_CALIBRATION_CATALOG=""
CIRCUIT_GATE_PLAN=""
MAX_TELEMETRY_FRAMES=1200
HTTP_TIMEOUT=20

while [ "${#}" -gt 0 ]; do
  case "$1" in
    --framework)
      FRAMEWORK="${2:-}"
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
    --decoders)
      DECODER_CSV="${2:-}"
      shift 2
      ;;
    --code-family)
      CODE_FAMILY="${2:-}"
      shift 2
      ;;
    --shots)
      SHOTS="${2:-}"
      shift 2
      ;;
    --distance)
      DISTANCE="${2:-}"
      shift 2
      ;;
    --rounds)
      ROUNDS="${2:-}"
      shift 2
      ;;
    --error-rate)
      ERROR_RATE="${2:-}"
      shift 2
      ;;
    --sigma)
      SIGMA="${2:-}"
      shift 2
      ;;
    --seed)
      SEED="${2:-}"
      shift 2
      ;;
    --emit-x-events)
      EMIT_X_EVENTS="${2:-}"
      shift 2
      ;;
    --emit-z-events)
      EMIT_Z_EVENTS="${2:-}"
      shift 2
      ;;
    --neural-model)
      NEURAL_MODEL="${2:-}"
      shift 2
      ;;
    --circuit-name)
      CIRCUIT_NAME="${2:-}"
      shift 2
      ;;
    --circuit-qubits)
      CIRCUIT_QUBITS="${2:-}"
      shift 2
      ;;
    --circuit-qasm)
      CIRCUIT_QASM="${2:-}"
      shift 2
      ;;
    --circuit-hardware-target)
      CIRCUIT_HARDWARE_TARGET="${2:-}"
      shift 2
      ;;
    --circuit-detector-model)
      CIRCUIT_DETECTOR_MODEL="${2:-}"
      shift 2
      ;;
    --circuit-noise-config)
      CIRCUIT_NOISE_CONFIG="${2:-}"
      shift 2
      ;;
    --circuit-compile-artifact)
      CIRCUIT_COMPILE_ARTIFACT="${2:-}"
      shift 2
      ;;
    --circuit-calibration-snapshot)
      CIRCUIT_CALIBRATION_SNAPSHOT="${2:-}"
      shift 2
      ;;
    --circuit-calibration-catalog)
      CIRCUIT_CALIBRATION_CATALOG="${2:-}"
      shift 2
      ;;
    --circuit-gate-plan)
      CIRCUIT_GATE_PLAN="${2:-}"
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

if [ -z "${FRAMEWORK}" ]; then
  echo "Error: --framework is required." >&2
  exit 1
fi
if [ -z "${RUN_ID}" ]; then
  echo "Error: --run-id is required." >&2
  exit 1
fi
if [ -z "${BACKEND_BASE_URL}" ] && [ -z "${TELEMETRY_URL}" ]; then
  echo "Error: provide --backend-base-url or --telemetry-url for telemetry push." >&2
  exit 1
fi

case "${FRAMEWORK}" in
  pennylane|qiskit|cirq) ;;
  *)
    echo "Error: --framework must be one of pennylane, qiskit, cirq." >&2
    exit 1
    ;;
esac

case "${CODE_FAMILY}" in
  surface|gkp) ;;
  *)
    echo "Error: --code-family must be 'surface' or 'gkp'." >&2
    exit 1
    ;;
esac

case "${SHOTS}" in
  ''|*[!0-9]*)
    echo "Error: --shots must be a positive integer." >&2
    exit 1
    ;;
esac
case "${DISTANCE}" in
  ''|*[!0-9]*)
    echo "Error: --distance must be a positive odd integer." >&2
    exit 1
    ;;
esac
case "${ROUNDS}" in
  ''|*[!0-9]*)
    echo "Error: --rounds must be a positive integer." >&2
    exit 1
    ;;
esac
case "${EMIT_X_EVENTS}" in
  0|1) ;;
  *)
    echo "Error: --emit-x-events must be 0 or 1." >&2
    exit 1
    ;;
esac
case "${EMIT_Z_EVENTS}" in
  0|1) ;;
  *)
    echo "Error: --emit-z-events must be 0 or 1." >&2
    exit 1
    ;;
esac
case "${MAX_TELEMETRY_FRAMES}" in
  ''|*[!0-9]*)
    echo "Error: --max-telemetry-frames must be a non-negative integer." >&2
    exit 1
    ;;
esac

if [ "${SHOTS}" -le 0 ] || [ "${ROUNDS}" -le 0 ]; then
  echo "Error: --shots and --rounds must be > 0." >&2
  exit 1
fi
if [ "${DISTANCE}" -lt 3 ] || [ $((DISTANCE % 2)) -eq 0 ]; then
  echo "Error: --distance must be odd and >= 3." >&2
  exit 1
fi
if [ "${EMIT_X_EVENTS}" -eq 0 ] && [ "${EMIT_Z_EVENTS}" -eq 0 ]; then
  echo "Error: at least one of --emit-x-events or --emit-z-events must be 1." >&2
  exit 1
fi
if [ -n "${CIRCUIT_QUBITS}" ] && [ -z "${CIRCUIT_GATE_PLAN}" ]; then
  echo "Error: --circuit-qubits requires --circuit-gate-plan." >&2
  exit 1
fi
if [ -n "${CIRCUIT_GATE_PLAN}" ]; then
  if [ -z "${CIRCUIT_HARDWARE_TARGET}" ]; then
    CIRCUIT_HARDWARE_TARGET="superconducting"
  fi
  case "${CIRCUIT_HARDWARE_TARGET}" in
    superconducting|trapped_ion|photonic) ;;
    *)
      echo "Error: --circuit-hardware-target must be superconducting, trapped_ion, or photonic." >&2
      exit 1
      ;;
  esac
  if [ "${FRAMEWORK}" != "pennylane" ] && [ "${CIRCUIT_HARDWARE_TARGET}" != "superconducting" ]; then
    echo "Error: ${FRAMEWORK} supports only --circuit-hardware-target=superconducting." >&2
    exit 1
  fi
  if [ -n "${CIRCUIT_DETECTOR_MODEL}" ]; then
    if [ "${CIRCUIT_HARDWARE_TARGET}" != "photonic" ]; then
      echo "Error: --circuit-detector-model is only valid for --circuit-hardware-target=photonic." >&2
      exit 1
    fi
    case "${CIRCUIT_DETECTOR_MODEL}" in
      threshold|pnr_approx) ;;
      *)
        echo "Error: --circuit-detector-model must be threshold or pnr_approx." >&2
        exit 1
        ;;
    esac
  fi
  if [ -z "${CIRCUIT_QUBITS}" ]; then
    echo "Error: --circuit-qubits is required when --circuit-gate-plan is provided." >&2
    exit 1
  fi
  case "${CIRCUIT_QUBITS}" in
    ''|*[!0-9]*)
      echo "Error: --circuit-qubits must be a positive integer." >&2
      exit 1
      ;;
  esac
  if [ "${CIRCUIT_QUBITS}" -le 0 ]; then
    echo "Error: --circuit-qubits must be > 0." >&2
    exit 1
  fi
  if [ -n "${CIRCUIT_CALIBRATION_SNAPSHOT}" ]; then
    case "${CIRCUIT_CALIBRATION_SNAPSHOT}" in
      *[!a-zA-Z0-9._-]*)
        echo "Error: --circuit-calibration-snapshot may only contain [a-zA-Z0-9._-]." >&2
        exit 1
        ;;
    esac
  fi
fi

if ! command -v awk >/dev/null 2>&1; then
  echo "Error: awk is required." >&2
  exit 1
fi

PY_BIN="$(examples_python_bin "${REPO_ROOT}")" || {
  echo "Error: python3 not found." >&2
  exit 1
}
BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"

"${PY_BIN}" - <<'PY' "${ERROR_RATE}" "${SIGMA}" "${HTTP_TIMEOUT}"
import math
import sys
try:
    error_rate = float(sys.argv[1])
    sigma = float(sys.argv[2])
    timeout = float(sys.argv[3])
except ValueError:
    raise SystemExit("Error: --error-rate, --sigma, and --http-timeout must be numeric.")
if not (0.0 <= error_rate <= 1.0):
    raise SystemExit("Error: --error-rate must be within [0,1].")
if not (sigma >= 0.0):
    raise SystemExit("Error: --sigma must be >= 0.")
if math.isnan(timeout) or math.isinf(timeout) or timeout <= 0.0:
    raise SystemExit("Error: --http-timeout must be > 0.")
PY

export LIDMAS_DECODERS="${DECODER_CSV}"
if [ -n "${NEURAL_MODEL}" ]; then
  export LIDMAS_NEURAL_MODEL="${NEURAL_MODEL}"
fi

DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

if [ "${#DECODERS[@]}" -eq 0 ]; then
  echo "Error: no valid decoders resolved." >&2
  exit 1
fi

NEURAL_MODEL_PATH="$(paper_neural_model_path)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RESULT_ROOT="$(results_dir_for "${REPO_ROOT}" "hardware_integration/simulators/${FRAMEWORK}")"
RUN_DIR="${RESULT_ROOT}/${TIMESTAMP}_${CODE_FAMILY}_run_${RUN_ID%%-*}"
REQ_DIR="${RUN_DIR}/01_generate_comparison_requests"
RESP_DIR="${RUN_DIR}/02_replay_decoder_matrix"
CFG_DIR="${RESP_DIR}/configs"
mkdir -p "${REQ_DIR}" "${RESP_DIR}" "${CFG_DIR}"

GEN_SCRIPT="${REPO_ROOT}/examples/paper_runs/paper_04/scripts/generate_comparison_requests.py"
CUSTOM_GEN_SCRIPT="${REPO_ROOT}/hardware_integration/simulators/generate_custom_circuit_requests.py"
MAKE_CFG="${REPO_ROOT}/examples/paper_runs/paper_03/scripts/make_decoder_config.py"
BASE_CFG="${REPO_ROOT}/schemas/surface_decoder_adapter_config.json"
PUSH_TELEMETRY_SCRIPT="${REPO_ROOT}/hardware_integration/xanadu/push_decoder_requests_telemetry.py"

case "${FRAMEWORK}" in
  pennylane)
    PENNYLANE_MODE="required"
    QISKIT_MODE="disabled"
    CIRQ_MODE="disabled"
    REQUEST_FILE="${REQ_DIR}/decoder_requests_pennylane.ndjson"
    ;;
  qiskit)
    PENNYLANE_MODE="disabled"
    QISKIT_MODE="required"
    CIRQ_MODE="disabled"
    REQUEST_FILE="${REQ_DIR}/decoder_requests_qiskit.ndjson"
    ;;
  cirq)
    PENNYLANE_MODE="disabled"
    QISKIT_MODE="disabled"
    CIRQ_MODE="required"
    REQUEST_FILE="${REQ_DIR}/decoder_requests_cirq.ndjson"
    ;;
esac

echo "[simulator] framework=${FRAMEWORK} family=${CODE_FAMILY} run_id=${RUN_ID}"
echo "[simulator] generating requests in ${REQ_DIR}"
if [ -n "${CIRCUIT_GATE_PLAN}" ]; then
  CIRCUIT_NAME="${CIRCUIT_NAME:-custom_design}"
  CUSTOM_ARGS=(
    --out-dir "${REQ_DIR}"
    --framework "${FRAMEWORK}"
    --shots "${SHOTS}"
    --distance "${DISTANCE}"
    --rounds "${ROUNDS}"
    --error-rate "${ERROR_RATE}"
    --sigma "${SIGMA}"
    --seed "${SEED}"
    --code-family "${CODE_FAMILY}"
    --circuit-name "${CIRCUIT_NAME}"
    --circuit-qubits "${CIRCUIT_QUBITS}"
    --circuit-hardware-target "${CIRCUIT_HARDWARE_TARGET}"
    --circuit-gate-plan "${CIRCUIT_GATE_PLAN}"
  )
  if [ -n "${CIRCUIT_QASM}" ]; then
    CUSTOM_ARGS+=(--circuit-qasm "${CIRCUIT_QASM}")
  fi
  if [ -n "${CIRCUIT_DETECTOR_MODEL}" ]; then
    CUSTOM_ARGS+=(--circuit-detector-model "${CIRCUIT_DETECTOR_MODEL}")
  fi
  if [ -n "${CIRCUIT_NOISE_CONFIG}" ]; then
    CUSTOM_ARGS+=(--circuit-noise-config "${CIRCUIT_NOISE_CONFIG}")
  fi
  if [ -n "${CIRCUIT_COMPILE_ARTIFACT}" ]; then
    CUSTOM_ARGS+=(--circuit-compile-artifact "${CIRCUIT_COMPILE_ARTIFACT}")
  fi
  if [ -n "${CIRCUIT_CALIBRATION_SNAPSHOT}" ]; then
    CUSTOM_ARGS+=(--circuit-calibration-snapshot "${CIRCUIT_CALIBRATION_SNAPSHOT}")
  fi
  if [ -n "${CIRCUIT_CALIBRATION_CATALOG}" ]; then
    CUSTOM_ARGS+=(--circuit-calibration-catalog "${CIRCUIT_CALIBRATION_CATALOG}")
  fi
  "${PY_BIN}" "${CUSTOM_GEN_SCRIPT}" "${CUSTOM_ARGS[@]}"
else
  "${PY_BIN}" "${GEN_SCRIPT}" \
    --out-dir "${REQ_DIR}" \
    --code-family "${CODE_FAMILY}" \
    --shots "${SHOTS}" \
    --distance "${DISTANCE}" \
    --rounds "${ROUNDS}" \
    --error-rate "${ERROR_RATE}" \
    --sigma "${SIGMA}" \
    --seed "${SEED}" \
    --emit-x-events "${EMIT_X_EVENTS}" \
    --emit-z-events "${EMIT_Z_EVENTS}" \
    --pennylane-mode "${PENNYLANE_MODE}" \
    --qiskit-mode "${QISKIT_MODE}" \
    --cirq-mode "${CIRQ_MODE}"
fi

if [ ! -f "${REQUEST_FILE}" ]; then
  echo "Error: expected request file not found: ${REQUEST_FILE}" >&2
  exit 1
fi

SUMMARY_FILE="${REQ_DIR}/summary_generation.json"
if [ ! -f "${SUMMARY_FILE}" ]; then
  echo "Error: summary file not found: ${SUMMARY_FILE}" >&2
  exit 1
fi

SELECTED_BACKEND="$("${PY_BIN}" - <<'PY' "${SUMMARY_FILE}" "${FRAMEWORK}"
import json
import sys
summary_path = sys.argv[1]
dataset = sys.argv[2]
with open(summary_path, "r", encoding="utf-8") as f:
    data = json.load(f)
rows = data.get("datasets", [])
for row in rows:
    if row.get("dataset") == dataset:
        print(str(row.get("source_backend", "")))
        raise SystemExit(0)
raise SystemExit(2)
PY
)"

if [ -z "${SELECTED_BACKEND}" ]; then
  echo "Error: selected source backend missing in summary." >&2
  exit 1
fi
if [ "${SELECTED_BACKEND}" = "synthetic_fallback" ]; then
  echo "Error: ${FRAMEWORK} generation fell back to synthetic path; refusing run." >&2
  exit 1
fi
echo "[simulator] source_backend=${SELECTED_BACKEND} (actual framework path confirmed)"

RESPONSES=()
for decoder in "${DECODERS[@]}"; do
  cfg_path="${CFG_DIR}/surface_decoder_adapter_config_${decoder}.json"
  if [ "${decoder}" = "neural_mwpm" ]; then
    "${PY_BIN}" "${MAKE_CFG}" \
      --base "${BASE_CFG}" \
      --decoder "${decoder}" \
      --neural-model "${NEURAL_MODEL_PATH}" \
      --out "${cfg_path}"
  else
    "${PY_BIN}" "${MAKE_CFG}" \
      --base "${BASE_CFG}" \
      --decoder "${decoder}" \
      --out "${cfg_path}"
  fi

  resp="${RESP_DIR}/decoder_responses_${FRAMEWORK}_${decoder}.ndjson"
  echo "[replay] decoder=${decoder} input=$(basename "${REQUEST_FILE}") output=$(basename "${resp}")"
  "${BIN}" --decoder_io_replay \
    --decoder_io_in="${REQUEST_FILE}" \
    --decoder_io_out="${resp}" \
    --decoder_io_config="${cfg_path}" \
    --decoder_io_continue_on_error
  RESPONSES+=("${resp}")
done

PRIMARY_DECODER="${DECODERS[0]}"
TELEMETRY_ARGS=(
  --input "${REQUEST_FILE}"
  --run-id "${RUN_ID}"
  --max-frames "${MAX_TELEMETRY_FRAMES}"
  --http-timeout "${HTTP_TIMEOUT}"
  --primary-decoder "${PRIMARY_DECODER}"
)
if [ -n "${TELEMETRY_URL}" ]; then
  TELEMETRY_ARGS+=(--telemetry-url "${TELEMETRY_URL}")
else
  TELEMETRY_ARGS+=(--backend-base-url "${BACKEND_BASE_URL}")
fi
for response_file in "${RESPONSES[@]}"; do
  TELEMETRY_ARGS+=(--responses "${response_file}")
done

echo "[telemetry] pushing exact telemetry to backend for run ${RUN_ID}"
"${PY_BIN}" "${PUSH_TELEMETRY_SCRIPT}" "${TELEMETRY_ARGS[@]}"

echo "[done] framework replay complete"
echo "[done] request_file=${REQUEST_FILE}"
echo "[done] responses_dir=${RESP_DIR}"
