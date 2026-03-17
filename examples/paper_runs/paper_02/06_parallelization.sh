#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

BIN="$(resolve_lidmas_binary "${REPO_ROOT}")"
ensure_examples_env "${REPO_ROOT}"
RESULT_DIR="$(paper_results_dir "06_parallelization")"
PY_BIN="$(paper_python_bin)"

TRIALS="${LIDMAS_PAR_TRIALS:-4000}"
D_VALUE="${LIDMAS_PAR_D:-5}"
DECODER="${LIDMAS_PAR_DECODER:-mwpm}"
SEED="${LIDMAS_PAR_SEED:-2026}"
PAR_THREADS="${LIDMAS_PAR_THREADS:-4}"

P_START="${LIDMAS_PAR_P_START:-0.04}"
P_END="${LIDMAS_PAR_P_END:-0.12}"
P_STEP="${LIDMAS_PAR_P_STEP:-0.01}"
SIGMA_START="${LIDMAS_PAR_SIGMA_START:-0.05}"
SIGMA_END="${LIDMAS_PAR_SIGMA_END:-0.35}"
SIGMA_STEP="${LIDMAS_PAR_SIGMA_STEP:-0.05}"

INCLUDE_GKP="${LIDMAS_PAR_INCLUDE_GKP:-1}"
INCLUDE_GPU="${LIDMAS_PAR_INCLUDE_GPU:-0}"
GKP_GATE="${LIDMAS_GKP_GATE:-0.005}"
GKP_MEAS="${LIDMAS_GKP_MEAS:-0.01}"
GKP_IDLE="${LIDMAS_GKP_IDLE:-0.005}"
GKP_LOSS="${LIDMAS_GKP_LOSS:-0.005}"
GKP_LOSS_MAP="${LIDMAS_GKP_LOSS_MAP:-}"

NEURAL_MODEL="$(paper_neural_model_path)"
if [ "${DECODER}" = "neural_mwpm" ] && [ ! -f "${NEURAL_MODEL}" ]; then
  echo "Error: decoder neural_mwpm requires model at ${NEURAL_MODEL}" >&2
  exit 1
fi

TIMINGS_CSV="${RESULT_DIR}/timings.csv"
echo "label,mode,threads,gpu,seconds,csv_path" > "${TIMINGS_CSV}"

run_case() {
  local label="$1"
  local mode="$2"
  local threads="$3"
  local gpu="$4"
  local out_csv="$5"
  local required="$6"

  local -a cmd=(
    "${BIN}" --engine=surface --surface_threshold
    --mode="${mode}"
    --decoder="${DECODER}"
    --d="${D_VALUE}"
    --trials="${TRIALS}"
    --seed="${SEED}"
    --threads="${threads}"
    --out="${out_csv}"
  )

  if [ "${mode}" = "pauli" ]; then
    cmd+=(--p_start="${P_START}" --p_end="${P_END}" --p_step="${P_STEP}")
  else
    cmd+=(--sigma_start="${SIGMA_START}" --sigma_end="${SIGMA_END}" --sigma_step="${SIGMA_STEP}")
    if [ -n "${GKP_GATE}" ]; then
      cmd+=(--gkp_gate="${GKP_GATE}")
    fi
    if [ -n "${GKP_MEAS}" ]; then
      cmd+=(--gkp_meas="${GKP_MEAS}")
    fi
    if [ -n "${GKP_IDLE}" ]; then
      cmd+=(--gkp_idle="${GKP_IDLE}")
    fi
    if [ -n "${GKP_LOSS}" ]; then
      cmd+=(--gkp_loss="${GKP_LOSS}")
    fi
    if [ -n "${GKP_LOSS_MAP}" ]; then
      cmd+=(--gkp_loss_map="${GKP_LOSS_MAP}")
    fi
  fi

  if [ "${DECODER}" = "neural_mwpm" ]; then
    cmd+=(--neural_model="${NEURAL_MODEL}")
  fi
  if [ "${gpu}" = "1" ]; then
    cmd+=(--gpu)
  fi

  echo "  -> ${label}"
  local start_ts
  local end_ts
  local elapsed
  start_ts="$("${PY_BIN}" -c 'import time; print(time.perf_counter())')"
  if "${cmd[@]}"; then
    end_ts="$("${PY_BIN}" -c 'import time; print(time.perf_counter())')"
    elapsed="$(awk -v s="${start_ts}" -v e="${end_ts}" 'BEGIN { printf "%.6f", (e - s) }')"
    printf "%s,%s,%s,%s,%s,%s\n" "${label}" "${mode}" "${threads}" "${gpu}" "${elapsed}" "${out_csv}" >> "${TIMINGS_CSV}"
    return 0
  fi

  if [ "${required}" = "1" ]; then
    echo "Error: required run '${label}' failed" >&2
    return 1
  fi
  echo "Warning: optional run '${label}' failed; skipping" >&2
  return 1
}

echo "Running paper experiment 06 (parallelization fidelity/throughput)..."
echo "Decoder: ${DECODER}"
echo "Distance: ${D_VALUE}"
echo "Trials per point: ${TRIALS}"
echo "Threads(serial/parallel): 1/${PAR_THREADS}"

run_case "pauli_serial" "pauli" "1" "0" "${RESULT_DIR}/pauli_serial.csv" "1"
run_case "pauli_threaded" "pauli" "${PAR_THREADS}" "0" "${RESULT_DIR}/pauli_threaded.csv" "1"

if [ "${INCLUDE_GPU}" = "1" ]; then
  run_case "pauli_gpu" "pauli" "${PAR_THREADS}" "1" "${RESULT_DIR}/pauli_gpu.csv" "0" || true
fi

if [ "${INCLUDE_GKP}" = "1" ]; then
  run_case "gkp_serial" "gkp" "1" "0" "${RESULT_DIR}/gkp_serial.csv" "1"
  run_case "gkp_threaded" "gkp" "${PAR_THREADS}" "0" "${RESULT_DIR}/gkp_threaded.csv" "1"
fi

"${PY_BIN}" "${SCRIPT_DIR}/scripts/summarize_parallelization.py" \
  --timings "${TIMINGS_CSV}" \
  --out-md "${RESULT_DIR}/table_parallelization.md" \
  --out-csv "${RESULT_DIR}/table_parallelization.csv"

echo "Paper run 06 complete: ${RESULT_DIR}"
