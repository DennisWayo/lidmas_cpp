#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_DIR="$(paper_results_dir "04_real_data_slice")"
OUT_DIR="$(paper_results_dir "05_real_data_analysis")"
mkdir -p "${OUT_DIR}"

if ! ls "${IN_DIR}"/decoder_responses_*_*.ndjson >/dev/null 2>&1; then
  "${SCRIPT_DIR}/04_real_data_slice.sh"
fi

DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)
decoder_csv="$(IFS=,; echo "${DECODERS[*]}")"

PY_BIN="$(paper_python_bin)"
ANALYZER="${SCRIPT_DIR}/scripts/analyze_replay_matrix.py"

"${PY_BIN}" "${ANALYZER}" \
  --requests-dir "${IN_DIR}" \
  --responses-dir "${IN_DIR}" \
  --decoders "${decoder_csv}" \
  --out-csv "${OUT_DIR}/table_real_data_decoder_matrix.csv" \
  --out-md "${OUT_DIR}/table_real_data_decoder_matrix.md"

echo "Wrote real-data analysis to ${OUT_DIR}"
