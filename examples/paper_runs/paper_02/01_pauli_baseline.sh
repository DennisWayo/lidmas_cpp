#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "01_pauli_baseline")"
PY_BIN="$(paper_python_bin)"

TRIALS="${LIDMAS_TRIALS:-3000}"
D_VALUE="${LIDMAS_D:-5}"
P_START="${LIDMAS_P_START:-0.03}"
P_END="${LIDMAS_P_END:-0.12}"
P_STEP="${LIDMAS_P_STEP:-0.01}"
SEED="${LIDMAS_SEED:-1337}"
THREADS="${LIDMAS_THREADS:-1}"

declare -a DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

echo "Running paper baseline experiment 01 (Pauli, fixed distance)..."
echo "Binary: ${BIN}"
echo "Trials per point: ${TRIALS}"
echo "Threads: ${THREADS}"
echo "Decoders: ${DECODERS[*]}"

MERGE_ARGS=()
for DECODER in "${DECODERS[@]}"; do
  OUT_CSV="${RESULT_DIR}/results_${DECODER}.csv"
  CMD=(
    "${BIN}" --surface_threshold
    --mode=pauli
    --decoder="${DECODER}"
    --d="${D_VALUE}"
    --p_start="${P_START}"
    --p_end="${P_END}"
    --p_step="${P_STEP}"
    --trials="${TRIALS}"
    --seed="${SEED}"
    --threads="${THREADS}"
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
  --output-prefix "${RESULT_DIR}/figure_pauli_baseline" \
  --mode pauli \
  --x-col pauli_p \
  --group-col decoder \
  --title "Pauli Decoder Comparison at d=${D_VALUE}" \
  --xlabel "Physical Pauli Error Rate p" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --logy

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_curve_table.py" \
  --input "${RESULT_DIR}/combined.csv" \
  --x-col pauli_p \
  --group-cols decoder \
  --out-md "${RESULT_DIR}/table_pauli_baseline.md" \
  --out-csv "${RESULT_DIR}/table_pauli_baseline.csv"

echo "Paper run 01 complete: ${RESULT_DIR}"
