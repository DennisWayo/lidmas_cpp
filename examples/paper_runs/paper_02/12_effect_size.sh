#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "12_effect_size")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

BOOTSTRAP="${LIDMAS_EFFECT_BOOTSTRAP:-2000}"
SEED="${LIDMAS_EFFECT_SEED:-1337}"
SOURCE_CSV="${REPO_ROOT}/examples/paper_runs/paper_02/results/02_gkp_baseline/combined.csv"

if [ ! -f "${SOURCE_CSV}" ]; then
  echo "Source baseline results not found. Running 02_gkp_baseline.sh first..."
  "${SCRIPT_DIR}/02_gkp_baseline.sh"
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_effect_size_bootstrap.py" \
  --input "${SOURCE_CSV}" \
  --bootstrap "${BOOTSTRAP}" \
  --seed "${SEED}" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --out-csv "${RESULT_DIR}/table_effect_size.csv" \
  --out-md "${RESULT_DIR}/table_effect_size.md" \
  --out-prefix "${RESULT_DIR}/figure_effect_size_heatmap"

echo "Paper run 12 complete: ${RESULT_DIR}"
