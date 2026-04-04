#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

PY_BIN="$(paper_python_bin)"
ANALYZER="${SCRIPT_DIR}/scripts/analyze_decoder_quality.py"
DISTANCE="${LIDMAS_SYNTH_DISTANCE:-5}"

DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)
decoder_csv="$(IFS=,; echo "${DECODERS[*]}")"

OUT_DIR="$(paper_results_dir "10_quality_metrics")"
mkdir -p "${OUT_DIR}"
RUN_SYNTH_ABLATION="${LIDMAS_RUN_SYNTH_ABLATION:-0}"

# Fixture quality metrics.
FIX_REQ="$(paper_results_dir "01_prepare_fixture_requests")"
FIX_RESP="$(paper_results_dir "02_replay_decoder_matrix")"
if ! ls "${FIX_RESP}"/decoder_responses_*_*.ndjson >/dev/null 2>&1; then
  "${SCRIPT_DIR}/02_replay_decoder_matrix.sh"
fi

"${PY_BIN}" "${ANALYZER}" \
  --requests-dir "${FIX_REQ}" \
  --responses-dir "${FIX_RESP}" \
  --decoders "${decoder_csv}" \
  --distance "${DISTANCE}" \
  --out-csv "${OUT_DIR}/table_fixture_quality.csv" \
  --out-md "${OUT_DIR}/table_fixture_quality.md"

# Real-data quality metrics (if available).
REAL_REQ="$(paper_results_dir "04_real_data_slice")"
if ls "${REAL_REQ}"/decoder_requests_*.ndjson >/dev/null 2>&1; then
  "${PY_BIN}" "${ANALYZER}" \
    --requests-dir "${REAL_REQ}" \
    --responses-dir "${REAL_REQ}" \
    --decoders "${decoder_csv}" \
    --distance "${DISTANCE}" \
    --out-csv "${OUT_DIR}/table_real_quality.csv" \
    --out-md "${OUT_DIR}/table_real_quality.md"
fi

if [ "${RUN_SYNTH_ABLATION}" = "1" ]; then
  # Synthetic heldout quality + logical-failure metrics.
  SYN_REQ="$(paper_results_dir "08_synthetic_matched_sparsity")"
  SYN_RESP="$(paper_results_dir "09_replay_synthetic_holdout")"
  if ! ls "${SYN_REQ}"/decoder_requests_synth_*_heldout.ndjson >/dev/null 2>&1; then
    "${SCRIPT_DIR}/08_prepare_synthetic_holdout.sh"
  fi
  if ! ls "${SYN_RESP}"/decoder_responses_synth_*_heldout_*.ndjson >/dev/null 2>&1; then
    "${SCRIPT_DIR}/09_replay_synthetic_holdout.sh"
  fi

  "${PY_BIN}" "${ANALYZER}" \
    --requests-dir "${SYN_REQ}" \
    --responses-dir "${SYN_RESP}" \
    --decoders "${decoder_csv}" \
    --distance "${DISTANCE}" \
    --request-glob "decoder_requests_synth_*_heldout.ndjson" \
    --out-csv "${OUT_DIR}/table_synthetic_heldout_quality.csv" \
    --out-md "${OUT_DIR}/table_synthetic_heldout_quality.md"
fi

echo "Wrote quality metrics to ${OUT_DIR}"
