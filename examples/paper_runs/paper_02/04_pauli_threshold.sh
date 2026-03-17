#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "04_pauli_threshold")"
PY_BIN="$(paper_python_bin)"

TRIALS="${LIDMAS_TRIALS:-4000}"
DISTANCES="${LIDMAS_DISTANCES:-3,5,7}"
P_START="${LIDMAS_P_START:-0.04}"
P_END="${LIDMAS_P_END:-0.12}"
P_STEP="${LIDMAS_P_STEP:-0.01}"
BOOTSTRAP="${LIDMAS_SCALING_BOOTSTRAP:-200}"
SEED="${LIDMAS_SEED:-1337}"
THREADS="${LIDMAS_THREADS:-1}"

declare -a DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

echo "Running paper experiment 04 (Pauli threshold/scaling)..."
echo "Distances: ${DISTANCES}"
echo "Trials per point: ${TRIALS}"
echo "Threads: ${THREADS}"
echo "Decoders: ${DECODERS[*]}"

SUMMARY_ARGS=()
for DECODER in "${DECODERS[@]}"; do
  OUT_CSV="${RESULT_DIR}/results_${DECODER}.csv"
  OUT_MD="${RESULT_DIR}/scaling_report_${DECODER}.md"
  OUT_JSON="${RESULT_DIR}/scaling_summary_${DECODER}.json"
  CMD=(
    "${BIN}" --surface_threshold
    --mode=pauli
    --decoder="${DECODER}"
    --d="${DISTANCES}"
    --p_start="${P_START}"
    --p_end="${P_END}"
    --p_step="${P_STEP}"
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
  echo "  -> ${DECODER}"
  "${CMD[@]}"

  run_publication_plot "${REPO_ROOT}" \
    --input "${OUT_CSV}" \
    --output-prefix "${RESULT_DIR}/figure_${DECODER}_pauli_threshold" \
    --mode pauli \
    --x-col pauli_p \
    --group-col distance \
    --group-prefix "d=" \
    --title "Pauli Threshold Dataset (${DECODER})" \
    --xlabel "Physical Pauli Error Rate p" \
    --ylabel "Logical Error Rate (LER)" \
    --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
    --logy

  SUMMARY_ARGS+=(--input "${DECODER}=${OUT_JSON}")
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_threshold_json.py" \
  "${SUMMARY_ARGS[@]}" \
  --out-md "${RESULT_DIR}/table_pauli_threshold_summary.md" \
  --out-csv "${RESULT_DIR}/table_pauli_threshold_summary.csv"

echo "Paper run 04 complete: ${RESULT_DIR}"
