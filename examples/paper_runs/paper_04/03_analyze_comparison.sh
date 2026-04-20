#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

REQUEST_DIR="$(paper_results_dir "01_generate_comparison_requests")"
REPLAY_DIR="$(paper_results_dir "02_replay_decoder_matrix")"
OUT_DIR="$(paper_results_dir "03_analysis")"
mkdir -p "${OUT_DIR}"

if ! ls "${REPLAY_DIR}"/decoder_responses_*.ndjson >/dev/null 2>&1; then
  "${SCRIPT_DIR}/02_replay_decoder_matrix.sh"
fi

PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

DECODER_CSV=""
while IFS= read -r decoder; do
  if [ -z "${DECODER_CSV}" ]; then
    DECODER_CSV="${decoder}"
  else
    DECODER_CSV="${DECODER_CSV},${decoder}"
  fi
done < <(paper_resolve_decoders)

"${PY_BIN}" "${REPO_ROOT}/examples/paper_runs/paper_03/scripts/analyze_replay_matrix.py" \
  --requests-dir "${REQUEST_DIR}" \
  --responses-dir "${REPLAY_DIR}" \
  --decoders "${DECODER_CSV}" \
  --out-csv "${OUT_DIR}/table_replay_matrix.csv" \
  --out-md "${OUT_DIR}/table_replay_matrix.md"

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_pennylane_vs_lidmas.py" \
  --matrix-csv "${OUT_DIR}/table_replay_matrix.csv" \
  --out-csv "${OUT_DIR}/table_source_vs_lidmas.csv" \
  --out-md "${OUT_DIR}/table_source_vs_lidmas.md" \
  --out-prefix "${OUT_DIR}/figure_source_vs_lidmas"

echo "paper_04 step 03 complete: ${OUT_DIR}"
