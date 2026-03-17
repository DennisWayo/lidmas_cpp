#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "05_gkp_threshold")"
PY_BIN="$(paper_python_bin)"

TRIALS="${LIDMAS_TRIALS:-1500}"
DISTANCES="${LIDMAS_DISTANCES:-3,5,7}"
SIGMA_START="${LIDMAS_SIGMA_START:-0.05}"
SIGMA_END="${LIDMAS_SIGMA_END:-0.35}"
SIGMA_STEP="${LIDMAS_SIGMA_STEP:-0.05}"
BOOTSTRAP="${LIDMAS_SCALING_BOOTSTRAP:-200}"
SEED="${LIDMAS_SEED:-1337}"
THREADS="${LIDMAS_THREADS:-1}"
GKP_GATE="${LIDMAS_GKP_GATE:-0.005}"
GKP_MEAS="${LIDMAS_GKP_MEAS:-0.01}"
GKP_IDLE="${LIDMAS_GKP_IDLE:-0.005}"
GKP_LOSS="${LIDMAS_GKP_LOSS:-0.005}"
GKP_LOSS_MAP="${LIDMAS_GKP_LOSS_MAP:-}"

declare -a DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

echo "Running paper experiment 05 (GKP threshold/crossing)..."
echo "Distances: ${DISTANCES}"
echo "Trials per point: ${TRIALS}"
echo "Threads: ${THREADS}"
echo "Decoders: ${DECODERS[*]}"

MERGE_ARGS=()
SUMMARY_ARGS=()
JSON_COUNT=0
for DECODER in "${DECODERS[@]}"; do
  OUT_CSV="${RESULT_DIR}/results_${DECODER}.csv"
  OUT_MD="${RESULT_DIR}/scaling_report_${DECODER}.md"
  OUT_JSON="${RESULT_DIR}/scaling_summary_${DECODER}.json"
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
    --estimate_threshold
    --scaling_fit
    --scaling_bootstrap="${BOOTSTRAP}"
    --scaling_report="${OUT_MD}"
    --scaling_json="${OUT_JSON}"
    --out="${OUT_CSV}"
  )
  if [ "${DECODER}" = "neural_mwpm" ]; then
    CMD+=(--neural_model="$(paper_neural_model_path)")
  fi
  if [ -n "${GKP_GATE}" ]; then
    CMD+=(--gkp_gate="${GKP_GATE}")
  fi
  if [ -n "${GKP_MEAS}" ]; then
    CMD+=(--gkp_meas="${GKP_MEAS}")
  fi
  if [ -n "${GKP_IDLE}" ]; then
    CMD+=(--gkp_idle="${GKP_IDLE}")
  fi
  if [ -n "${GKP_LOSS}" ]; then
    CMD+=(--gkp_loss="${GKP_LOSS}")
  fi
  if [ -n "${GKP_LOSS_MAP}" ]; then
    CMD+=(--gkp_loss_map="${GKP_LOSS_MAP}")
  fi
  echo "  -> ${DECODER}"
  "${CMD[@]}"

  run_publication_plot "${REPO_ROOT}" \
    --input "${OUT_CSV}" \
    --output-prefix "${RESULT_DIR}/figure_${DECODER}_gkp_threshold" \
    --mode gkp \
    --x-col sigma \
    --group-col distance \
    --group-prefix "d=" \
    --title "Native GKP Threshold Dataset (${DECODER})" \
    --xlabel "Sigma (GKP displacement std. dev.)" \
    --ylabel "Logical Error Rate (LER)" \
    --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
    --logy

  MERGE_ARGS+=(--input "${DECODER}=${OUT_CSV}")
  if [ -f "${OUT_JSON}" ]; then
    SUMMARY_ARGS+=(--input "${DECODER}=${OUT_JSON}")
    JSON_COUNT=$((JSON_COUNT + 1))
  fi
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/merge_surface_results.py" \
  "${MERGE_ARGS[@]}" \
  --out "${RESULT_DIR}/combined.csv"

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_hybrid_crossings.py" \
  "${MERGE_ARGS[@]}" \
  --out-md "${RESULT_DIR}/table_gkp_threshold_summary.md" \
  --out-csv "${RESULT_DIR}/table_gkp_threshold_summary.csv"

if [ "${JSON_COUNT}" -gt 0 ]; then
  "${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_threshold_json.py" \
    "${SUMMARY_ARGS[@]}" \
    --out-md "${RESULT_DIR}/table_gkp_scaling_summary.md" \
    --out-csv "${RESULT_DIR}/table_gkp_scaling_summary.csv"
else
  {
    echo "# Threshold Summary"
    echo
    echo "No scaling-summary JSON outputs were produced for mode=gkp."
  } > "${RESULT_DIR}/table_gkp_scaling_summary.md"
  {
    echo "reason"
    echo "no_scaling_summary_json_for_mode_gkp"
  } > "${RESULT_DIR}/table_gkp_scaling_summary.csv"
  echo "Warning: no scaling summary JSON files found; wrote placeholder scaling summary tables." >&2
fi

echo "Paper run 05 complete: ${RESULT_DIR}"
