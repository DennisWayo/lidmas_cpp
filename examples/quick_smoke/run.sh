#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "quick_smoke")"
TRIALS=80

cd "${REPO_ROOT}"
echo "Running quick smoke..."
"${BIN}" --smoke

"${BIN}" --surface_threshold \
  --mode=pauli \
  --decoder=mwpm \
  --d=3 \
  --p_start=0.02 \
  --p_end=0.08 \
  --p_step=0.02 \
  --trials="${TRIALS}" \
  --seed=1337 \
  --out="${RESULT_DIR}/surface_threshold.csv" \
  > /dev/null
echo "Quick smoke threshold mini-scan complete."

run_publication_plot "${REPO_ROOT}" \
  --input "${RESULT_DIR}/surface_threshold.csv" \
  --output-prefix "${RESULT_DIR}/figure_quick_smoke" \
  --mode pauli \
  --x-col pauli_p \
  --group-col distance \
  --group-prefix "d=" \
  --title "Quick Smoke Threshold Check" \
  --xlabel "Physical Pauli Error Rate p" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  > /dev/null
if [ ! -f "${RESULT_DIR}/figure_quick_smoke.png" ]; then
  echo "Error: figure generation failed." >&2
  exit 1
fi

echo "Figure written."
echo "Run complete."
