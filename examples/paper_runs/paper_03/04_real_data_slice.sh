#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "04_real_data_slice")"
CFG_DIR="${OUT_DIR}/configs"
mkdir -p "${OUT_DIR}" "${CFG_DIR}"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
BASE_CFG="${REPO_ROOT}/schemas/surface_decoder_adapter_config.json"
XANADU_DIR="${REPO_ROOT}/hardware_integration/xanadu"
FETCH_SCRIPT="${XANADU_DIR}/xandau_hardware_data.sh"
MAKE_CFG="${SCRIPT_DIR}/scripts/make_decoder_config.py"
PY_BIN="$(paper_python_bin)"
NEURAL_MODEL="$(paper_neural_model_path)"

MAX_SHOTS="${LIDMAS_HW_MAX_SHOTS:-5000}"
PROGRESS_EVERY="${LIDMAS_HW_PROGRESS_EVERY:-1000}"
DATASETS="${LIDMAS_HW_DATASETS:-aurora_min,qca_fig3b}"
FORCE_DOWNLOAD="${LIDMAS_HW_FORCE_DOWNLOAD:-0}"

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
echo "dataset,decoder,request_file,response_file,config_file" > "${manifest}"

IFS=',' read -r -a DATASET_LIST <<< "${DATASETS}"
for dataset in "${DATASET_LIST[@]}"; do
  dataset="${dataset//[[:space:]]/}"
  [ -z "${dataset}" ] && continue
  args=(
    --dataset "${dataset}"
    --max-shots "${MAX_SHOTS}"
    --progress-every "${PROGRESS_EVERY}"
    --skip-replay
  )
  if [ "${FORCE_DOWNLOAD}" = "1" ]; then
    args+=(--force-download)
  fi
  bash "${FETCH_SCRIPT}" "${args[@]}"

  case "${dataset}" in
    aurora_min)
      src_req="${REPO_ROOT}/examples/results/hardware_integration/decoder_requests_aurora_batch0_qpu5.ndjson"
      req_name="decoder_requests_aurora_batch0_qpu5.ndjson"
      ;;
    qca_fig3b)
      src_req="${REPO_ROOT}/examples/results/hardware_integration/decoder_requests_qca_fig3b.ndjson"
      req_name="decoder_requests_qca_fig3b.ndjson"
      ;;
    *)
      echo "Warning: unsupported dataset label '${dataset}', skipping copy/replay." >&2
      continue
      ;;
  esac

  if [ ! -f "${src_req}" ]; then
    echo "Error: expected request file not found after download: ${src_req}" >&2
    exit 1
  fi

  req_copy="${OUT_DIR}/${req_name}"
  cp "${src_req}" "${req_copy}"
  dataset_label="$(paper_dataset_label_from_request_path "${req_copy}")"

  for decoder in "${DECODERS[@]}"; do
    cfg_path="${CFG_DIR}/surface_decoder_adapter_config_${decoder}.json"
    resp="${OUT_DIR}/decoder_responses_${dataset_label}_${decoder}.ndjson"
    "${BIN}" --decoder_io_replay \
      --decoder_io_in="${req_copy}" \
      --decoder_io_out="${resp}" \
      --decoder_io_config="${cfg_path}" \
      --decoder_io_continue_on_error
    echo "${dataset_label},${decoder},$(basename "${req_copy}"),$(basename "${resp}"),$(basename "${cfg_path}")" >> "${manifest}"
  done
done

echo "Wrote real-data slice outputs to ${OUT_DIR}"
