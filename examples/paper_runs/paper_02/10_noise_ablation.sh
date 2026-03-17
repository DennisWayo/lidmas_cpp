#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "10_noise_ablation")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

TRIALS="${LIDMAS_ABLATION_TRIALS:-1200}"
D_VALUE="${LIDMAS_ABLATION_D:-5}"
SIGMA_REF="${LIDMAS_ABLATION_SIGMA_REF:-0.20}"
SIGMA_STEP="${LIDMAS_ABLATION_SIGMA_STEP:-0.01}"
SEED="${LIDMAS_ABLATION_SEED:-2026}"
THREADS="${LIDMAS_ABLATION_THREADS:-1}"
LEVELS_CSV="${LIDMAS_ABLATION_LEVELS:-0.0000,0.0025,0.0050,0.0100}"

BASE_GATE="${LIDMAS_GKP_GATE:-0.005}"
BASE_MEAS="${LIDMAS_GKP_MEAS:-0.01}"
BASE_IDLE="${LIDMAS_GKP_IDLE:-0.005}"
BASE_LOSS="${LIDMAS_GKP_LOSS:-0.005}"
GKP_LOSS_MAP="${LIDMAS_GKP_LOSS_MAP:-}"

IFS=',' read -r -a LEVELS <<< "${LEVELS_CSV}"
COMPONENTS=(gate meas idle loss)

declare -a DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

MANIFEST="${RESULT_DIR}/ablation_manifest.csv"
echo "decoder,component,level,seconds,csv_path" > "${MANIFEST}"

echo "Running paper experiment 10 (noise-component ablation)..."
echo "Decoders: ${DECODERS[*]}"
echo "Levels: ${LEVELS[*]}"

for DECODER in "${DECODERS[@]}"; do
  for COMPONENT in "${COMPONENTS[@]}"; do
    for LEVEL in "${LEVELS[@]}"; do
      GATE="${BASE_GATE}"
      MEAS="${BASE_MEAS}"
      IDLE="${BASE_IDLE}"
      LOSS="${BASE_LOSS}"
      case "${COMPONENT}" in
        gate) GATE="${LEVEL}" ;;
        meas) MEAS="${LEVEL}" ;;
        idle) IDLE="${LEVEL}" ;;
        loss) LOSS="${LEVEL}" ;;
      esac

      LEVEL_TAG="${LEVEL//./p}"
      LEVEL_TAG="${LEVEL_TAG//-/m}"
      OUT_CSV="${RESULT_DIR}/results_${DECODER}_${COMPONENT}_${LEVEL_TAG}.csv"

      CMD=(
        "${BIN}" --surface_threshold
        --mode=gkp
        --decoder="${DECODER}"
        --d="${D_VALUE}"
        --sigma_start="${SIGMA_REF}"
        --sigma_end="${SIGMA_REF}"
        --sigma_step="${SIGMA_STEP}"
        --trials="${TRIALS}"
        --seed="${SEED}"
        --threads="${THREADS}"
        --gkp_gate="${GATE}"
        --gkp_meas="${MEAS}"
        --gkp_idle="${IDLE}"
        --gkp_loss="${LOSS}"
        --out="${OUT_CSV}"
      )
      if [ -n "${GKP_LOSS_MAP}" ]; then
        CMD+=(--gkp_loss_map="${GKP_LOSS_MAP}")
      fi
      if [ "${DECODER}" = "neural_mwpm" ]; then
        CMD+=(--neural_model="$(paper_neural_model_path)")
      fi

      echo "  -> decoder=${DECODER} component=${COMPONENT} level=${LEVEL}"
      START_TS="$(${PY_BIN} -c 'import time; print(time.perf_counter())')"
      "${CMD[@]}"
      END_TS="$(${PY_BIN} -c 'import time; print(time.perf_counter())')"
      ELAPSED="$(awk -v s="${START_TS}" -v e="${END_TS}" 'BEGIN { printf "%.6f", (e - s) }')"

      printf "%s,%s,%s,%s,%s\n" "${DECODER}" "${COMPONENT}" "${LEVEL}" "${ELAPSED}" "${OUT_CSV}" >> "${MANIFEST}"
    done
  done
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_noise_ablation.py" \
  --manifest "${MANIFEST}" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --out-csv "${RESULT_DIR}/table_noise_ablation.csv" \
  --out-md "${RESULT_DIR}/table_noise_ablation.md" \
  --out-prefix "${RESULT_DIR}/figure_noise_ablation"

echo "Paper run 10 complete: ${RESULT_DIR}"
