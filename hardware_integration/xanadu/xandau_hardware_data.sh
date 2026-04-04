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
  --dataset <name>        Dataset preset:
                            aurora_min | aurora_full | qca_fig3b | gkp_fixture | gkp_full
                          (default: aurora_min)
  --max-shots <n>         Max shots to convert (default: 50000)
  --progress-every <n>    Progress print frequency (default: 10000)
  --skip-replay           Convert only; skip decoder replay
  --force-download        Re-download files even if cached locally
  --install-deps          Install missing Python deps (numpy) automatically
  --help                  Show this help

Examples:
  bash hardware_integration/xanadu/xandau_hardware_data.sh
  bash hardware_integration/xanadu/xandau_hardware_data.sh --dataset aurora_full --max-shots 0 --progress-every 50000
  bash hardware_integration/xanadu/xandau_hardware_data.sh --dataset gkp_full --max-shots 0
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
  mkdir -p "$(dirname "${out}")"
  if [ -f "${out}" ] && [ "${FORCE_DOWNLOAD}" -eq 0 ]; then
    echo "[download] cached: ${out}"
    return 0
  fi
  echo "[download] ${url}"
  curl --fail --location --retry 3 --retry-delay 2 --output "${out}" "${url}"
}

extract_tar_if_needed() {
  local tar_path="$1"
  local extract_root="$2"
  local marker="$3"

  if [ "${FORCE_DOWNLOAD}" -eq 1 ]; then
    rm -f "${marker}"
  fi

  if [ -f "${marker}" ]; then
    echo "[extract] cached: ${extract_root}"
    return 0
  fi

  echo "[extract] ${tar_path} -> ${extract_root}"
  mkdir -p "${extract_root}"
  tar -xzf "${tar_path}" -C "${extract_root}"
  touch "${marker}"
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

line_count_or_zero() {
  local path="$1"
  if [ -f "${path}" ]; then
    wc -l < "${path}"
  else
    echo 0
  fi
}

convert_aurora_batches() {
  local split_dir="$1"
  local mapping_file="$2"
  local qpu_count="$3"
  local req_out="$4"
  local split_label="$5"

  if [ ! -d "${split_dir}" ]; then
    echo "Error: Aurora split directory not found: ${split_dir}" >&2
    exit 1
  fi

  local -a batch_dirs=()
  local batch_dir
  while IFS= read -r batch_dir; do
    [ -z "${batch_dir}" ] && continue
    batch_dirs+=("${batch_dir}")
  done < <(find "${split_dir}" -mindepth 1 -maxdepth 1 -type d -name 'batch_*' | sort)

  if [ "${#batch_dirs[@]}" -eq 0 ]; then
    echo "Error: no Aurora batch directories found in ${split_dir}" >&2
    exit 1
  fi

  rm -f "${req_out}"

  local remaining="${MAX_SHOTS}"
  local first_write=1
  local before after delta batch_limit
  local -a args=()
  for batch_dir in "${batch_dirs[@]}"; do
    if [ "${MAX_SHOTS}" -gt 0 ] && [ "${remaining}" -le 0 ]; then
      break
    fi

    before="$(line_count_or_zero "${req_out}")"
    batch_limit=0
    if [ "${MAX_SHOTS}" -gt 0 ]; then
      batch_limit="${remaining}"
    fi

    args=(
      --source-format aurora_switch_dir
      --stream
      --input "${batch_dir}"
      --mapping "${mapping_file}"
      --aurora-qpu-count "${qpu_count}"
      --aurora-binarize
      --max-shots "${batch_limit}"
      --progress-every "${PROGRESS_EVERY}"
      --out "${req_out}"
      --meta source=aurora_s3
      --meta split="${split_label}"
      --meta batch="$(basename "${batch_dir}")"
    )
    if [ "${first_write}" -eq 0 ]; then
      args+=(--append-out)
    fi

    "${PY_BIN}" "${CONVERTER}" "${args[@]}"

    after="$(line_count_or_zero "${req_out}")"
    delta=$((after - before))
    if [ "${delta}" -lt 0 ]; then
      delta=0
    fi
    if [ "${MAX_SHOTS}" -gt 0 ]; then
      remaining=$((remaining - delta))
    fi
    first_write=0
  done

  if [ ! -s "${req_out}" ]; then
    echo "Error: Aurora conversion produced an empty output file: ${req_out}" >&2
    exit 1
  fi
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
GKP_COUNT_EXTRACTOR="${SCRIPT_DIR}/extract_gkp_counts_from_npz.py"

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

  aurora_full)
    require_cmd tar
    AURORA_FULL_SPLIT="${LIDMAS_AURORA_FULL_SPLIT:-signal}"
    AURORA_FULL_QPU_COUNT="${LIDMAS_AURORA_FULL_QPU_COUNT:-5}"
    AURORA_ROOT="${DOWNLOAD_ROOT}/aurora/full"
    AURORA_TAR="${AURORA_ROOT}/decoder_demo/decoder_demo.tar.gz"
    AURORA_SPLIT_DIR="${AURORA_ROOT}/decoder_demo/${AURORA_FULL_SPLIT}"
    AURORA_MAPPING="${SCRIPT_DIR}/xanadu_aurora_mapping_batch0_qpu5.json"

    download_file "https://xanadu-aurora-data.s3.amazonaws.com/decoder_demo/decoder_demo.tar.gz" "${AURORA_TAR}"
    extract_tar_if_needed "${AURORA_TAR}" "${AURORA_ROOT}" "${AURORA_ROOT}/decoder_demo/.extract_complete"

    REQ_OUT="${RESULT_DIR}/decoder_requests_aurora_full_${AURORA_FULL_SPLIT}.ndjson"
    convert_aurora_batches "${AURORA_SPLIT_DIR}" "${AURORA_MAPPING}" "${AURORA_FULL_QPU_COUNT}" "${REQ_OUT}" "${AURORA_FULL_SPLIT}"
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

  gkp_fixture|gkp|gkp_counts)
    REQ_OUT="${RESULT_DIR}/decoder_requests_gkp.ndjson"
    "${PY_BIN}" "${CONVERTER}" \
      --source-format count_table_json \
      --input "${SCRIPT_DIR}/xanadu_gkp_counts_example.json" \
      --mapping "${SCRIPT_DIR}/xanadu_gkp_mapping_example.json" \
      --out "${REQ_OUT}" \
      --max-shots "${MAX_SHOTS}" \
      --progress-every "${PROGRESS_EVERY}" \
      --sigma 0.10 \
      --gate-error-rate 0.0004 \
      --meas-error-rate 0.0006 \
      --idle-error-rate 0.0002 \
      --meta source=gkp_fixture \
      --meta split=counts_example
    ;;

  gkp_full)
    require_cmd tar
    GKP_ROOT="${DOWNLOAD_ROOT}/gkp/full"
    GKP_TAR="${GKP_ROOT}/data.tar.gz"
    GKP_COUNTS_JSON="${RESULT_DIR}/gkp_full_counts.json"
    GKP_FULL_EXPAND="${LIDMAS_GKP_FULL_EXPAND:-0}"

    download_file "https://xanadu-gkp-data.s3.amazonaws.com/data.tar.gz" "${GKP_TAR}"
    extract_tar_if_needed "${GKP_TAR}" "${GKP_ROOT}" "${GKP_ROOT}/.extract_complete"

    "${PY_BIN}" "${GKP_COUNT_EXTRACTOR}" \
      --input-root "${GKP_ROOT}" \
      --out "${GKP_COUNTS_JSON}"

    REQ_OUT="${RESULT_DIR}/decoder_requests_gkp_full.ndjson"
    gkp_args=(
      --source-format count_table_json \
      --input "${GKP_COUNTS_JSON}" \
      --mapping "${SCRIPT_DIR}/xanadu_gkp_mapping_example.json" \
      --out "${REQ_OUT}" \
      --max-shots "${MAX_SHOTS}" \
      --progress-every "${PROGRESS_EVERY}" \
      --sigma 0.10 \
      --gate-error-rate 0.0004 \
      --meas-error-rate 0.0006 \
      --idle-error-rate 0.0002 \
      --meta source=gkp_s3 \
      --meta split=full_npz_counts
    )
    if [ "${GKP_FULL_EXPAND}" != "1" ]; then
      gkp_args+=(--count-table-no-expand)
    fi
    "${PY_BIN}" "${CONVERTER}" "${gkp_args[@]}"
    ;;

  *)
    echo "Error: unsupported --dataset '${DATASET}'." >&2
    echo "Use one of: aurora_min, aurora_full, qca_fig3b, gkp_fixture, gkp_full." >&2
    exit 1
    ;;
esac

echo "[convert] wrote ${REQ_OUT}"
wc -l "${REQ_OUT}"

if [ "${RUN_REPLAY}" -eq 1 ]; then
  bash "${SCRIPT_DIR}/replay.sh" "${REQ_OUT}"
fi

echo "[done] dataset=${DATASET}"
