#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "08_crossing_bootstrap")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

BOOTSTRAP="${LIDMAS_CROSS_BOOTSTRAP:-1500}"
SEED="${LIDMAS_CROSS_SEED:-1337}"
SOURCE_DIR="${REPO_ROOT}/examples/paper_runs/paper_02/results/05_gkp_threshold"

if [ ! -f "${SOURCE_DIR}/results_mwpm.csv" ]; then
  echo "Source threshold results not found. Running 05_gkp_threshold.sh first..."
  "${SCRIPT_DIR}/05_gkp_threshold.sh"
fi

declare -a DECODERS=()
while IFS= read -r decoder; do
  DECODERS+=("${decoder}")
done < <(paper_resolve_decoders)

declare -a INPUT_ARGS=()
for DECODER in "${DECODERS[@]}"; do
  CSV_PATH="${SOURCE_DIR}/results_${DECODER}.csv"
  if [ -f "${CSV_PATH}" ]; then
    INPUT_ARGS+=(--input "${DECODER}=${CSV_PATH}")
  else
    echo "Warning: missing ${CSV_PATH}; skipping ${DECODER}" >&2
  fi
done

if [ "${#INPUT_ARGS[@]}" -eq 0 ]; then
  echo "Error: no decoder CSV inputs available for crossing bootstrap." >&2
  exit 1
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_crossing_bootstrap.py" \
  "${INPUT_ARGS[@]}" \
  --bootstrap "${BOOTSTRAP}" \
  --seed "${SEED}" \
  --style "${REPO_ROOT}/examples/plot_only/publication.mplstyle" \
  --out-csv "${RESULT_DIR}/table_crossing_bootstrap.csv" \
  --out-md "${RESULT_DIR}/table_crossing_bootstrap.md" \
  --out-prefix "${RESULT_DIR}/figure_crossing_bootstrap"

echo "Paper run 08 complete: ${RESULT_DIR}"
