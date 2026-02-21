#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RESULT_DIR="${REPO_ROOT}/examples/results/decoder_comparison"
BIN="${REPO_ROOT}/build/lidmas"
MODEL_PATH="${SCRIPT_DIR}/dummy_model.json"

TRIALS="${LIDMAS_TRIALS:-2000}"
D_VALUE="${LIDMAS_D:-5}"
P_START="${LIDMAS_P_START:-0.03}"
P_END="${LIDMAS_P_END:-0.12}"
P_STEP="${LIDMAS_P_STEP:-0.01}"

mkdir -p "${RESULT_DIR}"
rm -f \
  "${RESULT_DIR}/results_mwpm.csv" \
  "${RESULT_DIR}/results_uf.csv" \
  "${RESULT_DIR}/results_neural.csv" \
  "${RESULT_DIR}/decoder_comparison_combined.csv" \
  "${RESULT_DIR}/figure_decoder_comparison.png" \
  "${RESULT_DIR}/figure_decoder_comparison.pdf" \
  "${RESULT_DIR}/figure_decoder_comparison.svg" \
  "${RESULT_DIR}/decoder_comparison.csv" \
  "${RESULT_DIR}/mwpm_surface_threshold.csv" \
  "${RESULT_DIR}/uf_surface_threshold.csv" \
  "${RESULT_DIR}/neural_mwpm_surface_threshold.csv"

cd "${REPO_ROOT}"
echo "[1/6] Building lidmas..."
cmake -B build -S .
cmake --build build

if [ ! -x "${BIN}" ]; then
  echo "Error: expected binary not found at ${BIN}" >&2
  exit 1
fi
if [ ! -f "${MODEL_PATH}" ]; then
  echo "Error: missing neural demo model at ${MODEL_PATH}" >&2
  exit 1
fi

echo "[2/6] Running MWPM baseline..."
"${BIN}" \
  --surface_threshold \
  --mode=pauli \
  --d="${D_VALUE}" \
  --p_start="${P_START}" \
  --p_end="${P_END}" \
  --p_step="${P_STEP}" \
  --trials="${TRIALS}" \
  --decoder=mwpm \
  --output="${RESULT_DIR}/results_mwpm.csv"

echo "[3/6] Running Union-Find..."
"${BIN}" \
  --surface_threshold \
  --mode=pauli \
  --d="${D_VALUE}" \
  --p_start="${P_START}" \
  --p_end="${P_END}" \
  --p_step="${P_STEP}" \
  --trials="${TRIALS}" \
  --decoder=uf \
  --output="${RESULT_DIR}/results_uf.csv"

echo "[4/6] Running Neural-MWPM (dummy model)..."
"${BIN}" \
  --surface_threshold \
  --mode=pauli \
  --d="${D_VALUE}" \
  --p_start="${P_START}" \
  --p_end="${P_END}" \
  --p_step="${P_STEP}" \
  --trials="${TRIALS}" \
  --decoder=neural_mwpm \
  --neural_model="${MODEL_PATH}" \
  --output="${RESULT_DIR}/results_neural.csv"

PYTHON_BIN=""
if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
  PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Error: python3 not found; cannot merge/plot decoder comparison outputs." >&2
  exit 1
fi

CACHE_ROOT="${REPO_ROOT}/.cache"
HOME_ROOT="${CACHE_ROOT}/home"
XDG_CACHE="${HOME_ROOT}/.cache"
MPL_CACHE="${CACHE_ROOT}/matplotlib"
mkdir -p "${XDG_CACHE}/fontconfig" "${HOME_ROOT}/.matplotlib" "${MPL_CACHE}"

echo "[5/6] Merging CSV outputs..."
HOME="${HOME_ROOT}" XDG_CACHE_HOME="${XDG_CACHE}" MPLCONFIGDIR="${MPL_CACHE}" MPLBACKEND=Agg \
  "${PYTHON_BIN}" "${SCRIPT_DIR}/merge_results.py" \
  --mwpm "${RESULT_DIR}/results_mwpm.csv" \
  --uf "${RESULT_DIR}/results_uf.csv" \
  --neural "${RESULT_DIR}/results_neural.csv" \
  --out "${RESULT_DIR}/decoder_comparison_combined.csv"

echo "[6/6] Generating figures..."
HOME="${HOME_ROOT}" XDG_CACHE_HOME="${XDG_CACHE}" MPLCONFIGDIR="${MPL_CACHE}" MPLBACKEND=Agg \
  "${PYTHON_BIN}" "${SCRIPT_DIR}/plot_comparison.py" \
  --input "${RESULT_DIR}/decoder_comparison_combined.csv" \
  --out_dir "${RESULT_DIR}"

echo "Decoder comparison complete."
echo "Results: ${RESULT_DIR}"
