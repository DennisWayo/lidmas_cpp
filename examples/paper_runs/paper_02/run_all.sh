#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/01_pauli_baseline.sh"
"${SCRIPT_DIR}/02_gkp_baseline.sh"
"${SCRIPT_DIR}/03_gkp_multidistance.sh"
"${SCRIPT_DIR}/04_pauli_threshold.sh"
"${SCRIPT_DIR}/05_gkp_threshold.sh"
"${SCRIPT_DIR}/06_parallelization.sh"

if [ "${LIDMAS_RUN_ADVANCED_ANALYSIS:-0}" = "1" ]; then
  "${SCRIPT_DIR}/07_decoder_pareto.sh"
  "${SCRIPT_DIR}/08_crossing_bootstrap.sh"
  "${SCRIPT_DIR}/09_distance_gain_heatmap.sh"
  "${SCRIPT_DIR}/10_noise_ablation.sh"
  "${SCRIPT_DIR}/11_rank_stability.sh"
  "${SCRIPT_DIR}/12_effect_size.sh"
  "${SCRIPT_DIR}/13_threading_fidelity.sh"
  "${SCRIPT_DIR}/14_critical_window.sh"
fi

echo "All paper runs complete."
