#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "14_critical_window")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

TRIALS="${LIDMAS_CRIT_TRIALS:-2500}"
DISTANCES="${LIDMAS_CRIT_DISTANCES:-3,5,7}"
SIGMA_START="${LIDMAS_CRIT_SIGMA_START:-0.08}"
SIGMA_END="${LIDMAS_CRIT_SIGMA_END:-0.24}"
SIGMA_STEP="${LIDMAS_CRIT_SIGMA_STEP:-0.02}"
SEED="${LIDMAS_CRIT_SEED:-1337}"
THREADS="${LIDMAS_CRIT_THREADS:-1}"
GKP_GATE="${LIDMAS_GKP_GATE:-0.005}"
GKP_MEAS="${LIDMAS_GKP_MEAS:-0.01}"
GKP_IDLE="${LIDMAS_GKP_IDLE:-0.005}"
GKP_LOSS="${LIDMAS_GKP_LOSS:-0.005}"
GKP_LOSS_MAP="${LIDMAS_GKP_LOSS_MAP:-}"

declare -a DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

MERGE_ARGS=()

echo "Running paper experiment 14 (critical-window zoom)..."
echo "Sigma window: ${SIGMA_START} to ${SIGMA_END} step ${SIGMA_STEP}"
echo "Decoders: ${DECODERS[*]}"

for DECODER in "${DECODERS[@]}"; do
  OUT_CSV="${RESULT_DIR}/results_${DECODER}.csv"
  CMD=(
    "${BIN}" --surface_threshold
    --mode=gkp
    --decoder="${DECODER}"
    --d="${DISTANCES}"
    --sigma_start="${SIGMA_START}"
    --sigma_end="${SIGMA_END}"
    --sigma_step="${SIGMA_STEP}"
    --trials="${TRIALS}"
    --seed="${SEED}"
    --threads="${THREADS}"
    --gkp_gate="${GKP_GATE}"
    --gkp_meas="${GKP_MEAS}"
    --gkp_idle="${GKP_IDLE}"
    --gkp_loss="${GKP_LOSS}"
    --out="${OUT_CSV}"
  )
  if [ -n "${GKP_LOSS_MAP}" ]; then
    CMD+=(--gkp_loss_map="${GKP_LOSS_MAP}")
  fi
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

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_critical_window.py" \
  --input "${RESULT_DIR}/combined.csv" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --out-csv "${RESULT_DIR}/table_critical_window_crossings.csv" \
  --out-md "${RESULT_DIR}/table_critical_window_crossings.md" \
  --out-prefix "${RESULT_DIR}/figure_critical_window_zoom"

echo "Paper run 14 complete: ${RESULT_DIR}"
