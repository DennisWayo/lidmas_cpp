#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "hybrid_threshold")"

TRIALS="${LIDMAS_TRIALS:-2000}"

echo "Running Hybrid CV Surface Code Threshold Sweep..."
echo "Using binary: ${BIN}"
echo "Trials per point: ${TRIALS}"

cd "${REPO_ROOT}"
"${BIN}" --surface_threshold \
  --mode=hybrid \
  --decoder=mwpm \
  --d=3,5,7 \
  --sigma_start=0.05 \
  --sigma_end=0.6 \
  --sigma_step=0.05 \
  --trials="${TRIALS}" \
  --out="${RESULT_DIR}/surface_threshold.csv"

if [ -f "${REPO_ROOT}/plot_threshold.py" ]; then
  mv -f "${REPO_ROOT}/plot_threshold.py" "${RESULT_DIR}/plot_threshold.py"
fi
if [ -f "${REPO_ROOT}/threshold_plot.png" ]; then
  mv -f "${REPO_ROOT}/threshold_plot.png" "${RESULT_DIR}/threshold_plot.png"
fi

run_publication_plot "${REPO_ROOT}" \
  --input "${RESULT_DIR}/surface_threshold.csv" \
  --output-prefix "${RESULT_DIR}/figure_hybrid_threshold" \
  --mode hybrid \
  --x-col sigma \
  --group-col distance \
  --group-prefix "d=" \
  --title "Hybrid CV-Discrete Threshold Curve" \
  --xlabel "Sigma (CV displacement std. dev.)" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --logy

echo "Run complete."
