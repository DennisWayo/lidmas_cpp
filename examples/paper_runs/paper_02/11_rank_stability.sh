#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "11_rank_stability")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

BOOTSTRAP="${LIDMAS_RANK_BOOTSTRAP:-1500}"
SEED="${LIDMAS_RANK_SEED:-1337}"
SOURCE_CSV="${REPO_ROOT}/examples/paper_runs/paper_02/results/02_gkp_baseline/combined.csv"

if [ ! -f "${SOURCE_CSV}" ]; then
  echo "Source baseline results not found. Running 02_gkp_baseline.sh first..."
  "${SCRIPT_DIR}/02_gkp_baseline.sh"
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_rank_stability.py" \
  --input "${SOURCE_CSV}" \
  --bootstrap "${BOOTSTRAP}" \
  --seed "${SEED}" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --out-csv "${RESULT_DIR}/table_rank_stability.csv" \
  --out-md "${RESULT_DIR}/table_rank_stability.md" \
  --out-prefix "${RESULT_DIR}/figure_rank_stability"

echo "Paper run 11 complete: ${RESULT_DIR}"
