#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

SWEEP_DIR="$(paper_results_dir "05_scaling_sweep")"
RUN_ROOT="${SWEEP_DIR}/runs"
mkdir -p "${RUN_ROOT}"

SHOTS_CSV="${LIDMAS_P4_SCALING_SHOTS:-120,600,2400}"
MANIFEST="${SWEEP_DIR}/sweep_manifest.csv"
echo "shot,results_base,elapsed_generate_s,elapsed_replay_s,elapsed_analysis_s,elapsed_total_s" > "${MANIFEST}"

_orig_results_base_set=0
_orig_shots_set=0
_orig_results_base=""
_orig_shots=""

if [ -n "${LIDMAS_P4_RESULTS_BASE+x}" ]; then
  _orig_results_base_set=1
  _orig_results_base="${LIDMAS_P4_RESULTS_BASE}"
fi
if [ -n "${LIDMAS_P4_SHOTS+x}" ]; then
  _orig_shots_set=1
  _orig_shots="${LIDMAS_P4_SHOTS}"
fi

restore_env() {
  if [ "${_orig_results_base_set}" -eq 1 ]; then
    export LIDMAS_P4_RESULTS_BASE="${_orig_results_base}"
  else
    unset LIDMAS_P4_RESULTS_BASE || true
  fi

  if [ "${_orig_shots_set}" -eq 1 ]; then
    export LIDMAS_P4_SHOTS="${_orig_shots}"
  else
    unset LIDMAS_P4_SHOTS || true
  fi
}
trap restore_env EXIT

IFS=',' read -r -a SHOT_LIST <<< "${SHOTS_CSV}"
for shot_raw in "${SHOT_LIST[@]}"; do
  shot="${shot_raw//[[:space:]]/}"
  [ -n "${shot}" ] || continue
  if ! [[ "${shot}" =~ ^[0-9]+$ ]]; then
    echo "Warning: skipping invalid shot value '${shot}' in LIDMAS_P4_SCALING_SHOTS." >&2
    continue
  fi

  run_base="${RUN_ROOT}/shots_${shot}"
  mkdir -p "${run_base}"

  export LIDMAS_P4_RESULTS_BASE="${run_base}"
  export LIDMAS_P4_SHOTS="${shot}"

  echo "paper_04 scaling run: shots=${shot} base=${run_base}"
  t_total_start=$(date +%s)
  t0=$(date +%s); "${SCRIPT_DIR}/01_generate_comparison_requests.sh"; t1=$(date +%s)
  t2=$(date +%s); "${SCRIPT_DIR}/02_replay_decoder_matrix.sh"; t3=$(date +%s)
  t4=$(date +%s); "${SCRIPT_DIR}/03_analyze_comparison.sh"; t5=$(date +%s)
  t_total_end=$(date +%s)

  echo "${shot},${run_base},$((t1 - t0)),$((t3 - t2)),$((t5 - t4)),$((t_total_end - t_total_start))" >> "${MANIFEST}"
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_scaling_sweep.py" \
  --manifest "${MANIFEST}" \
  --out-csv "${SWEEP_DIR}/table_scaling_sweep.csv" \
  --out-md "${SWEEP_DIR}/table_scaling_sweep.md" \
  --out-decoder-csv "${SWEEP_DIR}/table_scaling_sweep_by_decoder.csv" \
  --out-prefix "${SWEEP_DIR}/figure_scaling_sweep"

echo "paper_04 step 05 complete: ${SWEEP_DIR}"
