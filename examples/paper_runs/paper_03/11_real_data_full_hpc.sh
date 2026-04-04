#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

RUN_NAME="${LIDMAS_FULL_RUN_NAME:-11_real_data_full_hpc}"
OUT_DIR="$(paper_results_dir "${RUN_NAME}")"
CFG_DIR="${OUT_DIR}/configs"
mkdir -p "${OUT_DIR}" "${CFG_DIR}"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
BASE_CFG="${REPO_ROOT}/schemas/surface_decoder_adapter_config.json"
XANADU_DIR="${REPO_ROOT}/hardware_integration/xanadu"
FETCH_SCRIPT="${XANADU_DIR}/xandau_hardware_data.sh"
MAKE_CFG="${SCRIPT_DIR}/scripts/make_decoder_config.py"
PY_BIN="$(paper_python_bin)"
NEURAL_MODEL="$(paper_neural_model_path)"

MAX_SHOTS="${LIDMAS_HW_MAX_SHOTS:-0}"
PROGRESS_EVERY="${LIDMAS_HW_PROGRESS_EVERY:-50000}"
DATASETS="${LIDMAS_HW_DATASETS:-aurora_full,qca_fig3b_full}"
FORCE_DOWNLOAD="${LIDMAS_HW_FORCE_DOWNLOAD:-0}"
REUSE_REQUESTS="${LIDMAS_HW_REUSE_REQUESTS:-1}"
REQUESTS_DIR="${LIDMAS_HW_REQUESTS_DIR:-}"
LINK_REQUESTS="${LIDMAS_HW_LINK_REQUESTS:-1}"

DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

for decoder in "${DECODERS[@]}"; do
  cfg_path="${CFG_DIR}/surface_decoder_adapter_config_${decoder}.json"
  if [ "${decoder}" = "neural_mwpm" ]; then
    "${PY_BIN}" "${MAKE_CFG}" \
      --base "${BASE_CFG}" \
      --decoder "${decoder}" \
      --neural-model "${NEURAL_MODEL}" \
      --out "${cfg_path}"
  else
    "${PY_BIN}" "${MAKE_CFG}" \
      --base "${BASE_CFG}" \
      --decoder "${decoder}" \
      --out "${cfg_path}"
  fi
done

manifest="${OUT_DIR}/replay_manifest.csv"
echo "dataset,decoder,request_file,response_file,config_file,source_request_path,max_shots" > "${manifest}"

IFS=',' read -r -a DATASET_LIST <<< "${DATASETS}"
for dataset in "${DATASET_LIST[@]}"; do
  dataset="${dataset//[[:space:]]/}"
  [ -z "${dataset}" ] && continue

  if ! fetch_dataset="$(paper_real_dataset_fetch_name "${dataset}")"; then
    echo "Warning: unsupported dataset label '${dataset}', skipping." >&2
    continue
  fi
  if ! req_name="$(paper_real_dataset_request_basename "${dataset}")"; then
    echo "Warning: unsupported dataset label '${dataset}', skipping." >&2
    continue
  fi

  if [ -n "${REQUESTS_DIR}" ]; then
    src_req="${REQUESTS_DIR%/}/${req_name}"
  else
    src_req="$(paper_real_dataset_request_path "${dataset}")"
    need_fetch=1
    if [ "${REUSE_REQUESTS}" = "1" ] && [ -f "${src_req}" ] && [ "${FORCE_DOWNLOAD}" = "0" ]; then
      need_fetch=0
    fi
    if [ "${need_fetch}" = "1" ]; then
      args=(
        --dataset "${fetch_dataset}"
        --max-shots "${MAX_SHOTS}"
        --progress-every "${PROGRESS_EVERY}"
        --skip-replay
      )
      if [ "${FORCE_DOWNLOAD}" = "1" ]; then
        args+=(--force-download)
      fi
      bash "${FETCH_SCRIPT}" "${args[@]}"
    fi
  fi

  if [ ! -f "${src_req}" ]; then
    echo "Error: expected request file not found: ${src_req}" >&2
    exit 1
  fi

  req_local="${OUT_DIR}/${req_name}"
  if [ "${LINK_REQUESTS}" = "1" ]; then
    src_abs="$(cd "$(dirname "${src_req}")" && pwd)/$(basename "${src_req}")"
    ln -sf "${src_abs}" "${req_local}"
  else
    cp "${src_req}" "${req_local}"
  fi
  dataset_label="$(paper_dataset_label_from_request_path "${req_local}")"

  for decoder in "${DECODERS[@]}"; do
    cfg_path="${CFG_DIR}/surface_decoder_adapter_config_${decoder}.json"
    resp="${OUT_DIR}/decoder_responses_${dataset_label}_${decoder}.ndjson"
    "${BIN}" --decoder_io_replay \
      --decoder_io_in="${req_local}" \
      --decoder_io_out="${resp}" \
      --decoder_io_config="${cfg_path}" \
      --decoder_io_continue_on_error
    echo "${dataset_label},${decoder},$(basename "${req_local}"),$(basename "${resp}"),$(basename "${cfg_path}"),${src_req},${MAX_SHOTS}" >> "${manifest}"
  done
done

echo "Wrote full-data HPC replay outputs to ${OUT_DIR}"
