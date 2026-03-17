#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "07_decoder_pareto")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

TRIALS="${LIDMAS_PARETO_TRIALS:-1500}"
D_VALUE="${LIDMAS_PARETO_D:-5}"
SIGMA_START="${LIDMAS_PARETO_SIGMA_START:-0.05}"
SIGMA_END="${LIDMAS_PARETO_SIGMA_END:-0.35}"
SIGMA_STEP="${LIDMAS_PARETO_SIGMA_STEP:-0.05}"
SIGMA_REF="${LIDMAS_PARETO_SIGMA_REF:-0.20}"
SEED="${LIDMAS_PARETO_SEED:-1337}"
THREADS="${LIDMAS_PARETO_THREADS:-1}"
GKP_GATE="${LIDMAS_GKP_GATE:-0.005}"
GKP_MEAS="${LIDMAS_GKP_MEAS:-0.01}"
GKP_IDLE="${LIDMAS_GKP_IDLE:-0.005}"
GKP_LOSS="${LIDMAS_GKP_LOSS:-0.005}"
GKP_LOSS_MAP="${LIDMAS_GKP_LOSS_MAP:-}"


declare -a DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

TIMINGS_CSV="${RESULT_DIR}/timings_decoder_pareto.csv"
echo "decoder,seconds,csv_path,distance" > "${TIMINGS_CSV}"

echo "Running paper experiment 07 (decoder Pareto frontier)..."
echo "Trials per point: ${TRIALS}"
echo "Decoders: ${DECODERS[*]}"

for DECODER in "${DECODERS[@]}"; do
  OUT_CSV="${RESULT_DIR}/results_${DECODER}.csv"
  CMD=(
    "${BIN}" --surface_threshold
    --mode=gkp
    --decoder="${DECODER}"
    --d="${D_VALUE}"
    --sigma_start="${SIGMA_START}"
    --sigma_end="${SIGMA_END}"
    --sigma_step="${SIGMA_STEP}"
    --trials="${TRIALS}"
    --seed="${SEED}"
    --threads="${THREADS}"
    --out="${OUT_CSV}"
    --gkp_gate="${GKP_GATE}"
    --gkp_meas="${GKP_MEAS}"
    --gkp_idle="${GKP_IDLE}"
    --gkp_loss="${GKP_LOSS}"
  )
  if [ -n "${GKP_LOSS_MAP}" ]; then
    CMD+=(--gkp_loss_map="${GKP_LOSS_MAP}")
  fi
  if [ "${DECODER}" = "neural_mwpm" ]; then
    CMD+=(--neural_model="$(paper_neural_model_path)")
  fi

  echo "  -> ${DECODER}"
  START_TS="$(${PY_BIN} -c 'import time; print(time.perf_counter())')"
  "${CMD[@]}"
  END_TS="$(${PY_BIN} -c 'import time; print(time.perf_counter())')"
  ELAPSED="$(awk -v s="${START_TS}" -v e="${END_TS}" 'BEGIN { printf "%.6f", (e - s) }')"

  printf "%s,%s,%s,%s\n" "${DECODER}" "${ELAPSED}" "${OUT_CSV}" "${D_VALUE}" >> "${TIMINGS_CSV}"
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_decoder_pareto.py" \
  --timings "${TIMINGS_CSV}" \
  --sigma-ref "${SIGMA_REF}" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --out-csv "${RESULT_DIR}/table_decoder_pareto.csv" \
  --out-md "${RESULT_DIR}/table_decoder_pareto.md" \
  --out-prefix "${RESULT_DIR}/figure_decoder_pareto"

echo "Paper run 07 complete: ${RESULT_DIR}"
