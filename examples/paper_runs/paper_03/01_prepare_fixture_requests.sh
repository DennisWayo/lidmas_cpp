#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "01_prepare_fixture_requests")"
XANADU_DIR="${REPO_ROOT}/hardware_integration/xanadu"
CONVERTER="${XANADU_DIR}/convert_xanadu_job_to_decoder_io.py"
PY_BIN="$(paper_python_bin)"

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

"${PY_BIN}" "${CONVERTER}" \
  --source-format xanadu_job_json \
  --input "${XANADU_DIR}/xanadu_job_result_example.json" \
  --mapping "${XANADU_DIR}/xanadu_syndrome_mapping_example.json" \
  --out "${OUT_DIR}/decoder_requests.ndjson" \
  --sigma 0.18 \
  --gate-error-rate 0.0007 \
  --meas-error-rate 0.0009 \
  --idle-error-rate 0.0003 \
  --meta calibration=2026-03-17

"${PY_BIN}" "${CONVERTER}" \
  --source-format aurora_switch_dir \
  --input "${XANADU_DIR}/aurora_batch_example" \
  --mapping "${XANADU_DIR}/xanadu_aurora_mapping_example.json" \
  --out "${OUT_DIR}/decoder_requests_aurora.ndjson" \
  --aurora-binarize \
  --sigma 0.16 \
  --gate-error-rate 0.0007 \
  --meas-error-rate 0.0009 \
  --idle-error-rate 0.0003 \
  --meta dataset=aurora_decoder_demo

"${PY_BIN}" "${CONVERTER}" \
  --source-format shot_matrix \
  --input "${XANADU_DIR}/xanadu_qca_samples_example.json" \
  --array-key samples \
  --mapping "${XANADU_DIR}/xanadu_qca_mapping_example.json" \
  --out "${OUT_DIR}/decoder_requests_qca.ndjson" \
  --sigma 0.12 \
  --gate-error-rate 0.0005 \
  --meas-error-rate 0.0008 \
  --idle-error-rate 0.0002 \
  --meta dataset=qca

"${PY_BIN}" "${CONVERTER}" \
  --source-format count_table_json \
  --input "${XANADU_DIR}/xanadu_gkp_counts_example.json" \
  --mapping "${XANADU_DIR}/xanadu_gkp_mapping_example.json" \
  --out "${OUT_DIR}/decoder_requests_gkp.ndjson" \
  --max-shots 1000 \
  --sigma 0.10 \
  --gate-error-rate 0.0004 \
  --meas-error-rate 0.0006 \
  --idle-error-rate 0.0002 \
  --meta dataset=gkp

{
  echo "dataset,request_file,request_lines"
  for req in "${OUT_DIR}"/decoder_requests*.ndjson; do
    [ -f "${req}" ] || continue
    dataset="$(paper_dataset_label_from_request_path "${req}")"
    lines="$(wc -l < "${req}")"
    echo "${dataset},$(basename "${req}"),${lines}"
  done
} > "${OUT_DIR}/table_request_manifest.csv"

echo "Wrote fixture request files to ${OUT_DIR}"
