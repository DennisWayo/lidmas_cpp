#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "03_hybrid_multidistance")"
PY_BIN="$(paper_python_bin)"

TRIALS="${LIDMAS_TRIALS:-3000}"
DISTANCES="${LIDMAS_DISTANCES:-3,5,7}"
SIGMA_START="${LIDMAS_SIGMA_START:-0.05}"
SIGMA_END="${LIDMAS_SIGMA_END:-0.60}"
SIGMA_STEP="${LIDMAS_SIGMA_STEP:-0.05}"
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

echo "Running paper experiment 03 (Hybrid, multi-distance)..."
echo "Distances: ${DISTANCES}"
echo "Trials per point: ${TRIALS}"

MERGE_ARGS=()
for DECODER in "${DECODERS[@]}"; do
  OUT_CSV="${RESULT_DIR}/results_${DECODER}.csv"
  CMD=(
    "${BIN}" --surface_threshold
    --mode=hybrid
    --decoder="${DECODER}"
    --d="${DISTANCES}"
    --sigma_start="${SIGMA_START}"
    --sigma_end="${SIGMA_END}"
    --sigma_step="${SIGMA_STEP}"
    --trials="${TRIALS}"
    --seed="${SEED}"
    --out="${OUT_CSV}"
  )
  if [ "${DECODER}" = "neural_mwpm" ]; then
    CMD+=(--neural_model="$(paper_neural_model_path)")
  fi
  echo "  -> ${DECODER}"
  "${CMD[@]}"
  MERGE_ARGS+=(--input "${DECODER}=${OUT_CSV}")

  run_publication_plot "${REPO_ROOT}" \
    --input "${OUT_CSV}" \
    --output-prefix "${RESULT_DIR}/figure_${DECODER}_multidistance" \
    --mode hybrid \
    --x-col sigma \
    --group-col distance \
    --group-prefix "d=" \
    --title "Hybrid Multi-Distance Trends (${DECODER})" \
    --xlabel "Sigma (CV displacement std. dev.)" \
    --ylabel "Logical Error Rate (LER)" \
    --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
    --logy
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/merge_surface_results.py" \
  "${MERGE_ARGS[@]}" \
  --out "${RESULT_DIR}/combined.csv"

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_curve_table.py" \
  --input "${RESULT_DIR}/combined.csv" \
  --x-col sigma \
  --group-cols decoder,distance \
  --out-md "${RESULT_DIR}/table_hybrid_multidistance.md" \
  --out-csv "${RESULT_DIR}/table_hybrid_multidistance.csv"

echo "Paper run 03 complete: ${RESULT_DIR}"

