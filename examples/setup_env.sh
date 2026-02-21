#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${SCRIPT_DIR}/common.sh"

echo "Setting up Python environment for examples..."
ensure_examples_env "${REPO_ROOT}"
echo "Environment ready: ${REPO_ROOT}/.venv"
echo "Generated outputs are written under: ${REPO_ROOT}/examples/results/"
echo "Run examples with:"
echo "  ${REPO_ROOT}/examples/hybrid_threshold/run.sh"
echo "  ${REPO_ROOT}/examples/pauli_threshold/run.sh"
echo "  ${REPO_ROOT}/examples/cv_demo/run.sh"
echo "  ${REPO_ROOT}/examples/quick_smoke/run.sh"
echo "  ${REPO_ROOT}/examples/scaling_fit/run.sh"
echo "  ${REPO_ROOT}/examples/adaptive_ci/run.sh"
echo "  ${REPO_ROOT}/examples/reproducibility_seed/run.sh"
echo "  ${REPO_ROOT}/examples/decoder_comparison/run.sh"
echo "  ${REPO_ROOT}/examples/failure_debug/run.sh"
echo "  ${REPO_ROOT}/examples/plot_only/run.sh <csv> <out_prefix> [mode] [x_col] [group_col] [title]"
