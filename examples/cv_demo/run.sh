#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "cv_demo")"

TRIALS="${LIDMAS_TRIALS:-200}"

echo "Running CV Gaussian -> GKP digitization demo..."
echo "Using binary: ${BIN}"
echo "Trials: ${TRIALS}"

cd "${REPO_ROOT}"
"${BIN}" --surface_threshold \
  --mode=hybrid \
  --decoder=mwpm \
  --d=3 \
  --cv_sigma=0.2 \
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
  --output-prefix "${RESULT_DIR}/figure_cv_demo" \
  --mode hybrid \
  --x-col sigma \
  --group-col distance \
  --group-prefix "d=" \
  --title "CV + GKP Single-Point Demo" \
  --xlabel "Sigma (CV displacement std. dev.)" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle"

echo "Demo complete."
