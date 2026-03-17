#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

IN_REQ_DIR="$(paper_results_dir "01_prepare_fixture_requests")"
IN_RESP_DIR="$(paper_results_dir "02_replay_decoder_matrix")"
OUT_DIR="$(paper_results_dir "03_decoder_matrix_analysis")"
mkdir -p "${OUT_DIR}"

if ! ls "${IN_RESP_DIR}"/decoder_responses_*_*.ndjson >/dev/null 2>&1; then
  "${SCRIPT_DIR}/02_replay_decoder_matrix.sh"
fi

DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)
decoder_csv="$(IFS=,; echo "${DECODERS[*]}")"

PY_BIN="$(paper_python_bin)"
ANALYZER="${SCRIPT_DIR}/scripts/analyze_replay_matrix.py"

"${PY_BIN}" "${ANALYZER}" \
  --requests-dir "${IN_REQ_DIR}" \
  --responses-dir "${IN_RESP_DIR}" \
  --decoders "${decoder_csv}" \
  --out-csv "${OUT_DIR}/table_decoder_matrix.csv" \
  --out-md "${OUT_DIR}/table_decoder_matrix.md"

echo "Wrote decoder matrix analysis to ${OUT_DIR}"
