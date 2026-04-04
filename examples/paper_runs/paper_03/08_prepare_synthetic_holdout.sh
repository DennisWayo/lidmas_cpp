#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_REAL_DIR="$(paper_results_dir "04_real_data_slice")"
OUT_DIR="$(paper_results_dir "08_synthetic_matched_sparsity")"
PY_BIN="$(paper_python_bin)"
GEN_SCRIPT="${SCRIPT_DIR}/scripts/generate_synthetic_matched_sparsity.py"

mkdir -p "${OUT_DIR}"

if ! ls "${IN_REAL_DIR}"/decoder_requests_*.ndjson >/dev/null 2>&1; then
  "${SCRIPT_DIR}/04_real_data_slice.sh"
fi

N_TRAIN="${LIDMAS_SYNTH_TRAIN_SHOTS:-1000}"
N_HELDOUT="${LIDMAS_SYNTH_HELDOUT_SHOTS:-500}"
SEED="${LIDMAS_SYNTH_SEED:-12345}"
DISTANCE="${LIDMAS_SYNTH_DISTANCE:-5}"

manifest="${OUT_DIR}/table_synthetic_manifest.csv"
echo "dataset,split,request_file,request_lines" > "${manifest}"

declare -a DATASETS=("aurora_batch0_qpu5" "qca_fig3b")
for dataset in "${DATASETS[@]}"; do
  ref_req="${IN_REAL_DIR}/decoder_requests_${dataset}.ndjson"
  if [ ! -f "${ref_req}" ]; then
    echo "Warning: missing real reference for '${dataset}', skipping synthetic match." >&2
    continue
  fi

  out_train="${OUT_DIR}/decoder_requests_synth_${dataset}_train.ndjson"
  out_heldout="${OUT_DIR}/decoder_requests_synth_${dataset}_heldout.ndjson"
  out_summary="${OUT_DIR}/summary_synth_${dataset}.json"

  "${PY_BIN}" "${GEN_SCRIPT}" \
    --reference "${ref_req}" \
    --dataset-label "synth_${dataset}" \
    --out-train "${out_train}" \
    --out-heldout "${out_heldout}" \
    --out-summary "${out_summary}" \
    --distance "${DISTANCE}" \
    --n-train "${N_TRAIN}" \
    --n-heldout "${N_HELDOUT}" \
    --seed "${SEED}"

  echo "synth_${dataset},train,$(basename "${out_train}"),$(wc -l < "${out_train}")" >> "${manifest}"
  echo "synth_${dataset},heldout,$(basename "${out_heldout}"),$(wc -l < "${out_heldout}")" >> "${manifest}"
done

echo "Wrote synthetic matched-sparsity requests to ${OUT_DIR}"

