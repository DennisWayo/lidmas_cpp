#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Repetition code.
"${SCRIPT_DIR}/01_build_syndrome_circuits.sh"
"${SCRIPT_DIR}/02_run_local_simulation.sh"
if [ "${LIDMAS_P5_HARDWARE:-0}" = "1" ]; then
  "${SCRIPT_DIR}/03_submit_ibm_runtime.sh"
else
  echo "paper_05 repetition: skipping IBM Runtime submission (set LIDMAS_P5_HARDWARE=1 to enable)."
fi
"${SCRIPT_DIR}/04_ingest_results.sh"
"${SCRIPT_DIR}/05_decode_live_syndromes.sh"
"${SCRIPT_DIR}/06_analyze_and_plot.sh"

# Compact CSS-LDPC/qLDPC-style code.
"${SCRIPT_DIR}/11_build_qldpc_syndrome_circuits.sh"
"${SCRIPT_DIR}/12_run_qldpc_local_simulation.sh"
if [ "${LIDMAS_P5_HARDWARE:-0}" = "1" ]; then
  "${SCRIPT_DIR}/13_submit_qldpc_ibm_runtime.sh"
else
  echo "paper_05 CSS-LDPC: skipping IBM Runtime submission (set LIDMAS_P5_HARDWARE=1 to enable)."
fi
"${SCRIPT_DIR}/14_ingest_qldpc_results.sh"
"${SCRIPT_DIR}/15_decode_qldpc_syndromes.sh"
"${SCRIPT_DIR}/16_analyze_qldpc.sh"

# Distance-5 surface-code Z-check branch.
"${SCRIPT_DIR}/21_build_surface_syndrome_circuits.sh"
"${SCRIPT_DIR}/22_run_surface_local_simulation.sh"
if [ "${LIDMAS_P5_HARDWARE:-0}" = "1" ]; then
  "${SCRIPT_DIR}/23_submit_surface_ibm_runtime.sh"
else
  echo "paper_05 surface: skipping IBM Runtime submission (set LIDMAS_P5_HARDWARE=1 to enable)."
fi
"${SCRIPT_DIR}/24_ingest_surface_results.sh"
"${SCRIPT_DIR}/25_decode_surface_syndromes.sh"
"${SCRIPT_DIR}/26_analyze_surface.sh"

# PennyLane-backed digitized-GKP companion branch. This branch has no IBM submission step.
"${SCRIPT_DIR}/31_build_gkp_digitized_model.sh"
"${SCRIPT_DIR}/32_run_gkp_digitized_sampler.sh"
"${SCRIPT_DIR}/33_ingest_gkp_results.sh"
"${SCRIPT_DIR}/34_decode_gkp_syndromes.sh"
"${SCRIPT_DIR}/35_analyze_gkp.sh"
"${SCRIPT_DIR}/36_render_gkp_figures.sh"

echo "paper_05 complete."
