#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${LIDMAS_P4_ENABLE_CODE_FAMILY:-1}" = "1" ]; then
  "${SCRIPT_DIR}/08_code_family_comparison.sh"
  if [ "${LIDMAS_P4_ENABLE_PARAM_SWEEPS:-0}" = "1" ]; then
    "${SCRIPT_DIR}/07_parametric_sweeps.sh"
  fi
  echo "paper_04 workflow complete."
  exit 0
fi

"${SCRIPT_DIR}/01_generate_comparison_requests.sh"
"${SCRIPT_DIR}/02_replay_decoder_matrix.sh"
"${SCRIPT_DIR}/03_analyze_comparison.sh"
"${SCRIPT_DIR}/04_extended_analysis.sh"
"${SCRIPT_DIR}/06_journal_plots.sh"

if [ "${LIDMAS_P4_ENABLE_PARAM_SWEEPS:-0}" = "1" ]; then
  "${SCRIPT_DIR}/07_parametric_sweeps.sh"
fi

if [ "${LIDMAS_P4_ENABLE_CODE_FAMILY:-0}" = "1" ]; then
  "${SCRIPT_DIR}/08_code_family_comparison.sh"
fi

echo "paper_04 workflow complete."
