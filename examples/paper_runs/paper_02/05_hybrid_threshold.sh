#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "05_hybrid_threshold")"
PY_BIN="$(paper_python_bin)"

TRIALS="${LIDMAS_TRIALS:-4000}"
DISTANCES="${LIDMAS_DISTANCES:-3,5,7}"
SIGMA_START="${LIDMAS_SIGMA_START:-0.05}"
SIGMA_END="${LIDMAS_SIGMA_END:-0.60}"
SIGMA_STEP="${LIDMAS_SIGMA_STEP:-0.05}"
BOOTSTRAP="${LIDMAS_SCALING_BOOTSTRAP:-200}"
SEED="${LIDMAS_SEED:-1337}"

declare -a DECODERS=("mwpm" "uf")
if paper_include_neural; then
  MODEL_PATH="$(paper_neural_model_path)"
  if [ -f "${MODEL_PATH}" ]; then
    DECODERS+=("neural_mwpm")
  else
    echo "Warning: neural model not found at ${MODEL_PATH}; skipping neural_mwpm" >&2
  fi
fi

echo "Running paper experiment 05 (Hybrid threshold/crossing)..."
echo "Distances: ${DISTANCES}"
echo "Trials per point: ${TRIALS}"

MERGE_ARGS=()
for DECODER in "${DECODERS[@]}"; do
  OUT_CSV="${RESULT_DIR}/results_${DECODER}.csv"
  OUT_MD="${RESULT_DIR}/scaling_report_${DECODER}.md"
  OUT_JSON="${RESULT_DIR}/scaling_summary_${DECODER}.json"
  echo "  -> ${DECODER}"
  CMD=(
    "${BIN}" --surface_threshold
    --mode=hybrid \
    --decoder="${DECODER}" \
    --d="${DISTANCES}" \
    --sigma_start="${SIGMA_START}" \
    --sigma_end="${SIGMA_END}" \
    --sigma_step="${SIGMA_STEP}" \
    --trials="${TRIALS}" \
    --seed="${SEED}" \
    --estimate_threshold \
    --scaling_fit \
    --scaling_bootstrap="${BOOTSTRAP}" \
    --scaling_report="${OUT_MD}" \
    --scaling_json="${OUT_JSON}" \
    --out="${OUT_CSV}"
  )
  if [ "${DECODER}" = "neural_mwpm" ]; then
    CMD+=(--neural_model="$(paper_neural_model_path)")
  fi
  "${CMD[@]}"

  run_publication_plot "${REPO_ROOT}" \
    --input "${OUT_CSV}" \
    --output-prefix "${RESULT_DIR}/figure_${DECODER}_hybrid_threshold" \
    --mode hybrid \
    --x-col sigma \
    --group-col distance \
    --group-prefix "d=" \
    --title "Hybrid Threshold Dataset (${DECODER})" \
    --xlabel "Sigma (CV displacement std. dev.)" \
    --ylabel "Logical Error Rate (LER)" \
    --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
    --logy

  MERGE_ARGS+=(--input "${DECODER}=${OUT_CSV}")
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/merge_surface_results.py" \
  "${MERGE_ARGS[@]}" \
  --out "${RESULT_DIR}/combined.csv"

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_hybrid_crossings.py" \
  "${MERGE_ARGS[@]}" \
  --out-md "${RESULT_DIR}/table_hybrid_threshold_summary.md" \
  --out-csv "${RESULT_DIR}/table_hybrid_threshold_summary.csv"

echo "Paper run 05 complete: ${RESULT_DIR}"
