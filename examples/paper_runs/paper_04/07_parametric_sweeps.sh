#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

OUT_DIR="$(paper_results_dir "07_parametric_sweeps")"
RUN_ROOT="${OUT_DIR}/runs"
mkdir -p "${RUN_ROOT}"

MANIFEST="${OUT_DIR}/parametric_manifest.csv"
echo "sweep_type,noise_rate,rounds,distance,shots,results_base,elapsed_generate_s,elapsed_replay_s,elapsed_analysis_s,elapsed_total_s" > "${MANIFEST}"

GRID_SHOTS="${LIDMAS_P4_GRID_SHOTS:-180}"
BASE_DISTANCE="${LIDMAS_P4_GRID_BASE_DISTANCE:-${LIDMAS_P4_DISTANCE:-5}}"
NOISES_CSV="${LIDMAS_P4_GRID_NOISES:-0.04,0.08,0.12}"
ROUNDS_CSV="${LIDMAS_P4_GRID_ROUNDS:-2,4,6}"

DISTANCES_CSV="${LIDMAS_P4_GRID_DISTANCES:-3,5,7}"
DIST_ERROR_RATE="${LIDMAS_P4_GRID_DISTANCE_ERROR_RATE:-${LIDMAS_P4_ERROR_RATE:-0.08}}"
DIST_ROUNDS="${LIDMAS_P4_GRID_DISTANCE_ROUNDS:-${LIDMAS_P4_ROUNDS:-4}}"

_orig_results_base_set=0
_orig_shots_set=0
_orig_error_rate_set=0
_orig_rounds_set=0
_orig_distance_set=0

_orig_results_base=""
_orig_shots=""
_orig_error_rate=""
_orig_rounds=""
_orig_distance=""

if [ -n "${LIDMAS_P4_RESULTS_BASE+x}" ]; then
  _orig_results_base_set=1
  _orig_results_base="${LIDMAS_P4_RESULTS_BASE}"
fi
if [ -n "${LIDMAS_P4_SHOTS+x}" ]; then
  _orig_shots_set=1
  _orig_shots="${LIDMAS_P4_SHOTS}"
fi
if [ -n "${LIDMAS_P4_ERROR_RATE+x}" ]; then
  _orig_error_rate_set=1
  _orig_error_rate="${LIDMAS_P4_ERROR_RATE}"
fi
if [ -n "${LIDMAS_P4_ROUNDS+x}" ]; then
  _orig_rounds_set=1
  _orig_rounds="${LIDMAS_P4_ROUNDS}"
fi
if [ -n "${LIDMAS_P4_DISTANCE+x}" ]; then
  _orig_distance_set=1
  _orig_distance="${LIDMAS_P4_DISTANCE}"
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
  if [ "${_orig_error_rate_set}" -eq 1 ]; then
    export LIDMAS_P4_ERROR_RATE="${_orig_error_rate}"
  else
    unset LIDMAS_P4_ERROR_RATE || true
  fi
  if [ "${_orig_rounds_set}" -eq 1 ]; then
    export LIDMAS_P4_ROUNDS="${_orig_rounds}"
  else
    unset LIDMAS_P4_ROUNDS || true
  fi
  if [ "${_orig_distance_set}" -eq 1 ]; then
    export LIDMAS_P4_DISTANCE="${_orig_distance}"
  else
    unset LIDMAS_P4_DISTANCE || true
  fi
}
trap restore_env EXIT

run_case() {
  local sweep_type="$1"
  local noise_rate="$2"
  local rounds="$3"
  local distance="$4"
  local shots="$5"
  local run_tag="$6"

  local run_base="${RUN_ROOT}/${run_tag}"
  mkdir -p "${run_base}"

  export LIDMAS_P4_RESULTS_BASE="${run_base}"
  export LIDMAS_P4_SHOTS="${shots}"
  export LIDMAS_P4_ERROR_RATE="${noise_rate}"
  export LIDMAS_P4_ROUNDS="${rounds}"
  export LIDMAS_P4_DISTANCE="${distance}"

  echo "paper_04 parametric run: type=${sweep_type} noise=${noise_rate} rounds=${rounds} distance=${distance} shots=${shots}"
  local t_total_start t_total_end t0 t1 t2 t3 t4 t5
  t_total_start=$(date +%s)
  t0=$(date +%s); "${SCRIPT_DIR}/01_generate_comparison_requests.sh"; t1=$(date +%s)
  t2=$(date +%s); "${SCRIPT_DIR}/02_replay_decoder_matrix.sh"; t3=$(date +%s)
  t4=$(date +%s); "${SCRIPT_DIR}/03_analyze_comparison.sh"; t5=$(date +%s)
  t_total_end=$(date +%s)

  echo "${sweep_type},${noise_rate},${rounds},${distance},${shots},${run_base},$((t1 - t0)),$((t3 - t2)),$((t5 - t4)),$((t_total_end - t_total_start))" >> "${MANIFEST}"
}

IFS=',' read -r -a NOISE_LIST <<< "${NOISES_CSV}"
IFS=',' read -r -a ROUND_LIST <<< "${ROUNDS_CSV}"
for noise_raw in "${NOISE_LIST[@]}"; do
  noise="${noise_raw//[[:space:]]/}"
  [ -n "${noise}" ] || continue
  for rounds_raw in "${ROUND_LIST[@]}"; do
    rounds="${rounds_raw//[[:space:]]/}"
    [ -n "${rounds}" ] || continue
    if ! [[ "${rounds}" =~ ^[0-9]+$ ]]; then
      echo "Warning: skipping invalid rounds value '${rounds}'." >&2
      continue
    fi
    noise_tag="${noise//./p}"
    run_case "noise_rounds" "${noise}" "${rounds}" "${BASE_DISTANCE}" "${GRID_SHOTS}" "noise_${noise_tag}_rounds_${rounds}"
  done
done

IFS=',' read -r -a DISTANCE_LIST <<< "${DISTANCES_CSV}"
for dist_raw in "${DISTANCE_LIST[@]}"; do
  dist="${dist_raw//[[:space:]]/}"
  [ -n "${dist}" ] || continue
  if ! [[ "${dist}" =~ ^[0-9]+$ ]]; then
    echo "Warning: skipping invalid distance value '${dist}'." >&2
    continue
  fi
  run_case "distance" "${DIST_ERROR_RATE}" "${DIST_ROUNDS}" "${dist}" "${GRID_SHOTS}" "distance_${dist}"
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_parametric_sweeps.py" \
  --manifest "${MANIFEST}" \
  --out-run-csv "${OUT_DIR}/table_parametric_runs.csv" \
  --out-noise-rounds-csv "${OUT_DIR}/table_noise_rounds_decoder.csv" \
  --out-distance-csv "${OUT_DIR}/table_distance_sweep_decoder.csv" \
  --out-prefix-noise-rounds "${OUT_DIR}/figure_noise_rounds_heatmap" \
  --out-prefix-distance "${OUT_DIR}/figure_distance_sweep"

echo "paper_04 step 07 complete: ${OUT_DIR}"
