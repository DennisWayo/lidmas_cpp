#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "adaptive_ci")"

MIN_TRIALS="${LIDMAS_MIN_TRIALS:-300}"
MAX_TRIALS="${LIDMAS_MAX_TRIALS:-5000}"
BATCH_TRIALS="${LIDMAS_BATCH_TRIALS:-200}"
TARGET_CI="${LIDMAS_TARGET_CI:-0.015}"

echo "Running adaptive-CI threshold example..."
echo "Using binary: ${BIN}"
echo "min_trials=${MIN_TRIALS} max_trials=${MAX_TRIALS} batch=${BATCH_TRIALS} target_ci=${TARGET_CI}"

cd "${REPO_ROOT}"
"${BIN}" --surface_threshold \
  --mode=pauli \
  --decoder=mwpm \
  --d=3,5,7 \
  --p_start=0.05 \
  --p_end=0.11 \
  --p_step=0.01 \
  --min_trials="${MIN_TRIALS}" \
  --max_trials="${MAX_TRIALS}" \
  --batch_trials="${BATCH_TRIALS}" \
  --target_ci_halfwidth="${TARGET_CI}" \
  --out="${RESULT_DIR}/surface_threshold.csv"

run_publication_plot "${REPO_ROOT}" \
  --input "${RESULT_DIR}/surface_threshold.csv" \
  --output-prefix "${RESULT_DIR}/figure_adaptive_ci" \
  --mode pauli \
  --x-col pauli_p \
  --group-col distance \
  --group-prefix "d=" \
  --title "Adaptive-CI Threshold Sweep (Pauli Mode)" \
  --xlabel "Physical Pauli Error Rate p" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --logy

echo "Adaptive-CI example complete."
