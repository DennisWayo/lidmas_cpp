#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "failure_debug")"

TRIALS="${LIDMAS_TRIALS:-400}"
DISTANCE="${LIDMAS_DISTANCE:-9}"
P_START="${LIDMAS_P_START:-0.18}"
P_END="${LIDMAS_P_END:-0.24}"
P_STEP="${LIDMAS_P_STEP:-0.02}"

ROOT_DUMP="${REPO_ROOT}/surface_decoder_failure_dump.txt"
LOCAL_DUMP="${RESULT_DIR}/surface_decoder_failure_dump.txt"

rm -f "${ROOT_DUMP}" "${LOCAL_DUMP}"

echo "Running failure-debug stress example..."
echo "Using binary: ${BIN}"
echo "d=${DISTANCE} p=[${P_START},${P_END}] step=${P_STEP} trials=${TRIALS}"

cd "${REPO_ROOT}"
"${BIN}" --surface_threshold \
  --mode=pauli \
  --decoder=mwpm \
  --d="${DISTANCE}" \
  --p_start="${P_START}" \
  --p_end="${P_END}" \
  --p_step="${P_STEP}" \
  --trials="${TRIALS}" \
  --out="${RESULT_DIR}/surface_threshold.csv"

if [ -f "${ROOT_DUMP}" ]; then
  cp "${ROOT_DUMP}" "${LOCAL_DUMP}"
  echo "Decoder failure dump captured at ${LOCAL_DUMP}"
else
  echo "No decoder failure dump generated in this run (this can be normal)."
fi

run_publication_plot "${REPO_ROOT}" \
  --input "${RESULT_DIR}/surface_threshold.csv" \
  --output-prefix "${RESULT_DIR}/figure_failure_debug" \
  --mode pauli \
  --x-col pauli_p \
  --group-col distance \
  --group-prefix "d=" \
  --title "Failure-Debug Stress Sweep" \
  --xlabel "Physical Pauli Error Rate p" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --logy

echo "Failure-debug example complete."
