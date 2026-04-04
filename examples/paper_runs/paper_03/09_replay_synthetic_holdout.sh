#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_DIR="$(paper_results_dir "08_synthetic_matched_sparsity")"
OUT_DIR="$(paper_results_dir "09_replay_synthetic_holdout")"
CFG_DIR="${OUT_DIR}/configs"
mkdir -p "${OUT_DIR}" "${CFG_DIR}"

if ! ls "${IN_DIR}"/decoder_requests_synth_*_heldout.ndjson >/dev/null 2>&1; then
  "${SCRIPT_DIR}/08_prepare_synthetic_holdout.sh"
fi

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
BASE_CFG="${REPO_ROOT}/schemas/surface_decoder_adapter_config.json"
MAKE_CFG="${SCRIPT_DIR}/scripts/make_decoder_config.py"
PY_BIN="$(paper_python_bin)"
NEURAL_MODEL="$(paper_neural_model_path)"

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

for req in "${IN_DIR}"/decoder_requests_synth_*_heldout.ndjson; do
  [ -f "${req}" ] || continue
  dataset="$(paper_dataset_label_from_request_path "${req}")"
  for decoder in "${DECODERS[@]}"; do
    cfg_path="${CFG_DIR}/surface_decoder_adapter_config_${decoder}.json"
    resp="${OUT_DIR}/decoder_responses_${dataset}_${decoder}.ndjson"
    "${BIN}" --decoder_io_replay \
      --decoder_io_in="${req}" \
      --decoder_io_out="${resp}" \
      --decoder_io_config="${cfg_path}" \
      --decoder_io_continue_on_error
    echo "${dataset},${decoder},$(basename "${req}"),$(basename "${resp}"),$(basename "${cfg_path}")" >> "${manifest}"
  done
done

echo "Wrote synthetic holdout replay outputs to ${OUT_DIR}"

