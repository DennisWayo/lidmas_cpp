#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(results_dir_for "${REPO_ROOT}" "reproducibility_seed")"

SEED="${LIDMAS_SEED:-424242}"
TRIALS="${LIDMAS_TRIALS:-500}"

CSV_A="${RESULT_DIR}/run_a.csv"
CSV_B="${RESULT_DIR}/run_b.csv"
NORMA="${RESULT_DIR}/run_a_normalized.csv"
NORMB="${RESULT_DIR}/run_b_normalized.csv"
DIFF_OUT="${RESULT_DIR}/reproducibility_diff.txt"
REPORT_OUT="${RESULT_DIR}/reproducibility_report.txt"

echo "Running reproducibility check with fixed seed..."
echo "Using binary: ${BIN}"
echo "seed=${SEED} trials=${TRIALS}"

cd "${REPO_ROOT}"
"${BIN}" --surface_threshold \
  --mode=hybrid \
  --decoder=mwpm \
  --d=3,5 \
  --sigma_start=0.30 \
  --sigma_end=0.60 \
  --sigma_step=0.10 \
  --trials="${TRIALS}" \
  --seed="${SEED}" \
  --out="${CSV_A}"

"${BIN}" --surface_threshold \
  --mode=hybrid \
  --decoder=mwpm \
  --d=3,5 \
  --sigma_start=0.30 \
  --sigma_end=0.60 \
  --sigma_step=0.10 \
  --trials="${TRIALS}" \
  --seed="${SEED}" \
  --out="${CSV_B}"

# Drop timestamp column for deterministic comparison.
cut -d, -f1-13 "${CSV_A}" > "${NORMA}"
cut -d, -f1-13 "${CSV_B}" > "${NORMB}"

if diff -u "${NORMA}" "${NORMB}" > "${DIFF_OUT}"; then
  echo "PASS: results match after removing timestamp column." | tee "${REPORT_OUT}"
else
  echo "FAIL: reproducibility mismatch detected (see ${DIFF_OUT})." | tee "${REPORT_OUT}"
  exit 1
fi

run_publication_plot "${REPO_ROOT}" \
  --input "${CSV_A}" \
  --output-prefix "${RESULT_DIR}/figure_reproducibility_seed" \
  --mode hybrid \
  --x-col sigma \
  --group-col distance \
  --group-prefix "d=" \
  --title "Reproducibility Seed Check (Hybrid Mode)" \
  --xlabel "Sigma (CV displacement std. dev.)" \
  --ylabel "Logical Error Rate (LER)" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --logy

echo "Reproducibility example complete."
