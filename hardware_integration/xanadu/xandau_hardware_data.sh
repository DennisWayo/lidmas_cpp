#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

usage() {
  cat <<'USAGE'
Usage:
  bash hardware_integration/xanadu/xandau_hardware_data.sh [options]

Options:
  --dataset <name>        Dataset preset: aurora_min | qca_fig3b (default: aurora_min)
  --max-shots <n>         Max shots to convert (default: 50000)
  --progress-every <n>    Progress print frequency (default: 10000)
  --skip-replay           Convert only; skip decoder replay
  --force-download        Re-download files even if cached locally
  --install-deps          Install missing Python deps (numpy) automatically
  --help                  Show this help

Examples:
  bash hardware_integration/xanadu/xandau_hardware_data.sh
  bash hardware_integration/xanadu/xandau_hardware_data.sh --dataset qca_fig3b --max-shots 200000
USAGE
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Error: required command '${cmd}' not found." >&2
    exit 1
  fi
}

download_file() {
  local url="$1"
  local out="$2"
  if [ -f "${out}" ] && [ "${FORCE_DOWNLOAD}" -eq 0 ]; then
    echo "[download] cached: ${out}"
    return 0
  fi
  echo "[download] ${url}"
  curl --fail --location --retry 3 --retry-delay 2 --output "${out}" "${url}"
}

ensure_numpy() {
  local py="$1"
  if "${py}" -c "import numpy" >/dev/null 2>&1; then
    return 0
  fi
  if [ "${INSTALL_DEPS}" -eq 1 ]; then
    echo "[deps] installing numpy into Python environment (${py})"
    "${py}" -m pip install --upgrade numpy
    return 0
  fi
  echo "Error: numpy is required. Re-run with --install-deps or run:" >&2
  echo "  ${py} -m pip install --upgrade numpy" >&2
  exit 1
}

DATASET="aurora_min"
MAX_SHOTS=50000
PROGRESS_EVERY=10000
RUN_REPLAY=1
FORCE_DOWNLOAD=0
INSTALL_DEPS=0

while [ "${#}" -gt 0 ]; do
  case "$1" in
    --dataset)
      DATASET="${2:-}"
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
    --skip-replay)
      RUN_REPLAY=0
      shift
      ;;
    --force-download)
      FORCE_DOWNLOAD=1
      shift
      ;;
    --install-deps)
      INSTALL_DEPS=1
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

require_cmd curl
PY_BIN="$(examples_python_bin "${REPO_ROOT}")" || {
  echo "Error: python3 not found." >&2
  exit 1
}
ensure_numpy "${PY_BIN}"

RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hardware_integration")"
DOWNLOAD_ROOT="${RESULT_DIR}/downloads"
CONVERTER="${SCRIPT_DIR}/convert_xanadu_job_to_decoder_io.py"

case "${DATASET}" in
  aurora_min)
    DATA_DIR="${DOWNLOAD_ROOT}/aurora/signal_batch_0_min"
    mkdir -p "${DATA_DIR}"
    BASE_URL="https://xanadu-aurora-data.s3.amazonaws.com/decoder_demo/signal/batch_0"
    for i in 0 1 2 3 4; do
      download_file "${BASE_URL}/switch_settings_qpu_${i}.npy" "${DATA_DIR}/switch_settings_qpu_${i}.npy"
    done

    REQ_OUT="${RESULT_DIR}/decoder_requests_aurora_batch0_qpu5.ndjson"
    "${PY_BIN}" "${CONVERTER}" \
      --source-format aurora_switch_dir \
      --stream \
      --input "${DATA_DIR}" \
      --mapping "${SCRIPT_DIR}/xanadu_aurora_mapping_batch0_qpu5.json" \
      --aurora-qpu-count 5 \
      --aurora-binarize \
      --max-shots "${MAX_SHOTS}" \
      --progress-every "${PROGRESS_EVERY}" \
      --out "${REQ_OUT}" \
      --meta source=aurora_s3 \
      --meta split=signal_batch_0_qpu_0_4
    ;;

  qca_fig3b)
    DATA_DIR="${DOWNLOAD_ROOT}/qca/fig3b"
    mkdir -p "${DATA_DIR}"
    BASE_URL="https://qca-data.s3.amazonaws.com/fig3b"
    download_file "${BASE_URL}/samples.npy" "${DATA_DIR}/samples.npy"
    download_file "${BASE_URL}/program_params.json" "${DATA_DIR}/program_params.json"

    REQ_OUT="${RESULT_DIR}/decoder_requests_qca_fig3b.ndjson"
    "${PY_BIN}" "${CONVERTER}" \
      --source-format shot_matrix \
      --stream \
      --input "${DATA_DIR}/samples.npy" \
      --mapping "${SCRIPT_DIR}/xanadu_qca_mapping_example.json" \
      --max-shots "${MAX_SHOTS}" \
      --progress-every "${PROGRESS_EVERY}" \
      --out "${REQ_OUT}" \
      --meta source=qca_s3 \
      --meta split=fig3b
    ;;

  *)
    echo "Error: unsupported --dataset '${DATASET}'. Use aurora_min or qca_fig3b." >&2
    exit 1
    ;;
esac

echo "[convert] wrote ${REQ_OUT}"
wc -l "${REQ_OUT}"

if [ "${RUN_REPLAY}" -eq 1 ]; then
  bash "${SCRIPT_DIR}/replay.sh" "${REQ_OUT}"
fi

echo "[done] dataset=${DATASET}"
