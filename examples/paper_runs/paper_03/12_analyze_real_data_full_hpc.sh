#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_NAME="${LIDMAS_FULL_RUN_NAME:-11_real_data_full_hpc}"
OUT_NAME="${LIDMAS_FULL_ANALYSIS_NAME:-12_real_data_full_analysis}"
IN_DIR="$(paper_results_dir "${IN_NAME}")"
OUT_DIR="$(paper_results_dir "${OUT_NAME}")"
mkdir -p "${OUT_DIR}"

if ! ls "${IN_DIR}"/decoder_responses_*_*.ndjson >/dev/null 2>&1; then
  "${SCRIPT_DIR}/11_real_data_full_hpc.sh"
fi

DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)
decoder_csv="$(IFS=,; echo "${DECODERS[*]}")"

PY_BIN="$(paper_python_bin)"
MATRIX_ANALYZER="${SCRIPT_DIR}/scripts/analyze_replay_matrix.py"
QUALITY_ANALYZER="${SCRIPT_DIR}/scripts/analyze_decoder_quality.py"
DISTANCE="${LIDMAS_SYNTH_DISTANCE:-5}"

"${PY_BIN}" "${MATRIX_ANALYZER}" \
  --requests-dir "${IN_DIR}" \
  --responses-dir "${IN_DIR}" \
  --decoders "${decoder_csv}" \
  --out-csv "${OUT_DIR}/table_full_data_decoder_matrix.csv" \
  --out-md "${OUT_DIR}/table_full_data_decoder_matrix.md"

"${PY_BIN}" "${QUALITY_ANALYZER}" \
  --requests-dir "${IN_DIR}" \
  --responses-dir "${IN_DIR}" \
  --decoders "${decoder_csv}" \
  --distance "${DISTANCE}" \
  --out-csv "${OUT_DIR}/table_full_data_quality.csv" \
  --out-md "${OUT_DIR}/table_full_data_quality.md"

echo "Wrote full-data HPC analysis outputs to ${OUT_DIR}"
