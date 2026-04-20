#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

OUT_DIR="$(paper_results_dir "01_generate_comparison_requests")"
PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

if [ -z "${PY_BIN}" ]; then
  echo "Error: python3 not found." >&2
  exit 1
fi

SHOTS="${LIDMAS_P4_SHOTS:-2500}"
CODE_FAMILY="${LIDMAS_P4_CODE_FAMILY:-surface}"
DISTANCE="${LIDMAS_P4_DISTANCE:-5}"
ROUNDS="${LIDMAS_P4_ROUNDS:-4}"
N_QUBITS="${LIDMAS_P4_N_QUBITS:-40}"
N_SYNDROME="${LIDMAS_P4_N_SYNDROME:-20}"
ERROR_RATE="${LIDMAS_P4_ERROR_RATE:-0.08}"
SIGMA="${LIDMAS_P4_SIGMA:-0.18}"
SEED="${LIDMAS_P4_SEED:-20260409}"
EMIT_X_EVENTS="${LIDMAS_P4_EMIT_X_EVENTS:-0}"
EMIT_Z_EVENTS="${LIDMAS_P4_EMIT_Z_EVENTS:-1}"
PENNYLANE_MODE="${LIDMAS_P4_PENNYLANE_MODE:-auto}"
QISKIT_MODE="${LIDMAS_P4_QISKIT_MODE:-auto}"
CIRQ_MODE="${LIDMAS_P4_CIRQ_MODE:-auto}"

echo "Running paper_04 request generation..."
echo "Output directory: ${OUT_DIR}"
echo "Code family: ${CODE_FAMILY}"
echo "Shots: ${SHOTS}"
echo "Distance: ${DISTANCE}"
echo "Repeated rounds: ${ROUNDS}"
echo "Legacy syndrome override (ignored by geometry): ${N_SYNDROME}"
echo "Emit X events: ${EMIT_X_EVENTS}"
echo "Emit Z events: ${EMIT_Z_EVENTS}"
echo "PennyLane mode: ${PENNYLANE_MODE}"
echo "Qiskit mode: ${QISKIT_MODE}"
echo "Cirq mode: ${CIRQ_MODE}"

"${PY_BIN}" "${SCRIPT_DIR}/scripts/generate_comparison_requests.py" \
  --out-dir "${OUT_DIR}" \
  --code-family "${CODE_FAMILY}" \
  --shots "${SHOTS}" \
  --distance "${DISTANCE}" \
  --rounds "${ROUNDS}" \
  --n-qubits "${N_QUBITS}" \
  --n-syndrome "${N_SYNDROME}" \
  --error-rate "${ERROR_RATE}" \
  --sigma "${SIGMA}" \
  --seed "${SEED}" \
  --emit-x-events "${EMIT_X_EVENTS}" \
  --emit-z-events "${EMIT_Z_EVENTS}" \
  --pennylane-mode "${PENNYLANE_MODE}" \
  --qiskit-mode "${QISKIT_MODE}" \
  --cirq-mode "${CIRQ_MODE}"

echo "paper_04 step 01 complete: ${OUT_DIR}"
