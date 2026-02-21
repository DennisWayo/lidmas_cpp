#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "pauli_threshold")"

TRIALS="${LIDMAS_TRIALS:-2000}"

echo "Running Pauli Surface Code Threshold Sweep..."
echo "Using binary: ${BIN}"
echo "Trials per point: ${TRIALS}"

cd "${REPO_ROOT}"
"${BIN}" --surface_threshold \
  --mode=pauli \
  --decoder=mwpm \
  --d=3,5,7 \
  --p_start=0.01 \
  --p_end=0.15 \
  --p_step=0.01 \
  --trials="${TRIALS}" \
  --out="${RESULT_DIR}/surface_threshold.csv"

run_publication_plot "${REPO_ROOT}" \
  --input "${RESULT_DIR}/surface_threshold.csv" \
  --output-prefix "${RESULT_DIR}/figure_pauli_threshold" \
  --mode pauli \
  --x-col pauli_p \
  --group-col distance \
  --group-prefix "d=" \
  --title "Pauli Surface-Code Threshold Curve" \
  --xlabel "Physical Pauli Error Rate p" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --logy

echo "Run complete."
