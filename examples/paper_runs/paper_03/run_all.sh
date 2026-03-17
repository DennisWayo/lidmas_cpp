#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/01_prepare_fixture_requests.sh"
"${SCRIPT_DIR}/02_replay_decoder_matrix.sh"
"${SCRIPT_DIR}/03_analyze_decoder_matrix.sh"

if [ "${LIDMAS_RUN_REAL_DATA:-0}" = "1" ]; then
  "${SCRIPT_DIR}/04_real_data_slice.sh"
  "${SCRIPT_DIR}/05_analyze_real_data_slice.sh"
fi

"${SCRIPT_DIR}/07_generate_figures.sh"

if [ "${LIDMAS_SYNC_PAPER_03_TEX:-1}" = "1" ] && [ -f "${SCRIPT_DIR}/../../../paper_03.tex" ]; then
  "${SCRIPT_DIR}/06_sync_tables_to_tex.sh"
fi

echo "paper_03 workflow complete."
