#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "scaling_fit")"

TRIALS="${LIDMAS_TRIALS:-2000}"
BOOTSTRAP="${LIDMAS_SCALING_BOOTSTRAP:-200}"

echo "Running finite-size scaling fit example..."
echo "Using binary: ${BIN}"
echo "Trials per point: ${TRIALS}"
echo "Bootstrap samples: ${BOOTSTRAP}"

cd "${REPO_ROOT}"
"${BIN}" --surface_threshold \
  --mode=pauli \
  --decoder=mwpm \
  --d=3,5,7 \
  --p_start=0.04 \
  --p_end=0.12 \
  --p_step=0.01 \
  --trials="${TRIALS}" \
  --estimate_threshold \
  --scaling_fit \
  --scaling_bootstrap="${BOOTSTRAP}" \
  --scaling_report="${RESULT_DIR}/scaling_report.md" \
  --scaling_json="${RESULT_DIR}/scaling_summary.json" \
  --out="${RESULT_DIR}/surface_threshold.csv"

run_publication_plot "${REPO_ROOT}" \
  --input "${RESULT_DIR}/surface_threshold.csv" \
  --output-prefix "${RESULT_DIR}/figure_scaling_fit" \
  --mode pauli \
  --x-col pauli_p \
  --group-col distance \
  --group-prefix "d=" \
  --title "Finite-Size Scaling Dataset (Pauli Mode)" \
  --xlabel "Physical Pauli Error Rate p" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --logy

echo "Scaling fit example complete."
