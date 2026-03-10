#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "02_hybrid_baseline")"
PY_BIN="$(paper_python_bin)"

TRIALS="${LIDMAS_TRIALS:-3000}"
D_VALUE="${LIDMAS_D:-5}"
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

echo "Running paper baseline experiment 02 (Hybrid, fixed distance)..."
echo "Binary: ${BIN}"
echo "Trials per point: ${TRIALS}"

MERGE_ARGS=()
for DECODER in "${DECODERS[@]}"; do
  OUT_CSV="${RESULT_DIR}/results_${DECODER}.csv"
  CMD=(
    "${BIN}" --surface_threshold
    --mode=hybrid
    --decoder="${DECODER}"
    --d="${D_VALUE}"
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
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/merge_surface_results.py" \
  "${MERGE_ARGS[@]}" \
  --out "${RESULT_DIR}/combined.csv"

run_publication_plot "${REPO_ROOT}" \
  --input "${RESULT_DIR}/combined.csv" \
  --output-prefix "${RESULT_DIR}/figure_hybrid_baseline" \
  --mode hybrid \
  --x-col sigma \
  --group-col decoder \
  --title "Hybrid Decoder Comparison at d=${D_VALUE}" \
  --xlabel "Sigma (CV displacement std. dev.)" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --logy

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_curve_table.py" \
  --input "${RESULT_DIR}/combined.csv" \
  --x-col sigma \
  --group-cols decoder \
  --out-md "${RESULT_DIR}/table_hybrid_baseline.md" \
  --out-csv "${RESULT_DIR}/table_hybrid_baseline.csv"

echo "Paper run 02 complete: ${RESULT_DIR}"

