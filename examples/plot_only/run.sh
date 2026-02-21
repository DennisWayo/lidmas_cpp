#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/examples/common.sh"

if [ $# -lt 2 ]; then
  cat <<'EOF'
Usage:
  ./examples/plot_only/run.sh <csv_path> <output_prefix> [mode] [x_col] [group_col] [title]

Examples:
  ./examples/plot_only/run.sh \
    examples/results/hybrid_threshold/surface_threshold.csv \
    examples/results/hybrid_threshold/figure_hybrid_threshold \
    hybrid sigma distance "Hybrid CV Threshold (MWPM)"
EOF
  exit 1
fi

CSV_PATH="$1"
OUTPUT_PREFIX="$2"
MODE="${3:-}"
X_COL="${4:-sigma}"
GROUP_COL="${5:-distance}"
TITLE="${6:-LiDMaS Publication Figure}"

ensure_examples_env "${REPO_ROOT}"
PY_BIN="$(examples_python_bin "${REPO_ROOT}")"

"${PY_BIN}" "${SCRIPT_DIR}/publish_plot.py" \
  --input "${CSV_PATH}" \
  --output-prefix "${OUTPUT_PREFIX}" \
  --mode "${MODE}" \
  --x-col "${X_COL}" \
  --group-col "${GROUP_COL}" \
  --group-prefix "d=" \
  --title "${TITLE}" \
  --style "${SCRIPT_DIR}/publication.mplstyle" \
  --logy
