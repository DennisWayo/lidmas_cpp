#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

REQUEST_DIR="$(paper_results_dir "01_generate_comparison_requests")"
REPLAY_DIR="$(paper_results_dir "02_replay_decoder_matrix")"
ANALYSIS_DIR="$(paper_results_dir "03_analysis")"
OUT_DIR="$(paper_results_dir "04_extended_analysis")"
mkdir -p "${OUT_DIR}"

if [ ! -f "${ANALYSIS_DIR}/table_replay_matrix.csv" ]; then
  "${SCRIPT_DIR}/03_analyze_comparison.sh"
fi

PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

REFERENCE_DATASET="${LIDMAS_P4_REFERENCE_DATASET:-lidmas_reference}"
BOOTSTRAP="${LIDMAS_P4_BOOTSTRAP:-2000}"
BOOTSTRAP_SEED="${LIDMAS_P4_BOOTSTRAP_SEED:-20260409}"

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_request_equivalence.py" \
  --requests-dir "${REQUEST_DIR}" \
  --reference-dataset "${REFERENCE_DATASET}" \
  --out-csv "${OUT_DIR}/table_request_equivalence.csv" \
  --out-md "${OUT_DIR}/table_request_equivalence.md" \
  --out-prefix "${OUT_DIR}/figure_request_equivalence"

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_bootstrap_ci.py" \
  --matrix-csv "${ANALYSIS_DIR}/table_replay_matrix.csv" \
  --responses-dir "${REPLAY_DIR}" \
  --reference-dataset "${REFERENCE_DATASET}" \
  --bootstrap "${BOOTSTRAP}" \
  --seed "${BOOTSTRAP_SEED}" \
  --out-metrics-csv "${OUT_DIR}/table_bootstrap_metrics.csv" \
  --out-metrics-md "${OUT_DIR}/table_bootstrap_metrics.md" \
  --out-delta-csv "${OUT_DIR}/table_bootstrap_source_vs_reference.csv" \
  --out-delta-md "${OUT_DIR}/table_bootstrap_source_vs_reference.md" \
  --out-prefix "${OUT_DIR}/figure_bootstrap_ci"

SUMMARY_MD="${OUT_DIR}/summary_extended_analysis.md"
cat > "${SUMMARY_MD}" <<EOF
# paper_04 Extended Analysis Summary

This stage adds three research-tightening outputs:

1. **Pre-decoder source equivalence audit**
   - Table: \`table_request_equivalence.csv\`
   - Figure: \`figure_request_equivalence.(png|pdf)\`
2. **Bootstrap uncertainty for decoder metrics and source-vs-reference deltas**
   - Tables: \`table_bootstrap_metrics.csv\`, \`table_bootstrap_source_vs_reference.csv\`
   - Figure: \`figure_bootstrap_ci.(png|pdf|svg)\`
3. **Optional scaling sweep**
   - Enable with \`LIDMAS_P4_ENABLE_SCALING=1\`
   - Outputs under \`results/05_scaling_sweep/\`

Reference dataset: \`${REFERENCE_DATASET}\`  
Bootstrap samples: \`${BOOTSTRAP}\`  
Bootstrap seed: \`${BOOTSTRAP_SEED}\`
EOF

if [ "${LIDMAS_P4_ENABLE_SCALING:-0}" = "1" ]; then
  "${SCRIPT_DIR}/05_scaling_sweep.sh"
fi

echo "paper_04 step 04 complete: ${OUT_DIR}"
