#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${REPO_ROOT}/examples/common.sh"

paper_results_dir() {
  local name="$1"
  local dir="${REPO_ROOT}/examples/paper_runs/paper_01/results/${name}"
  mkdir -p "${dir}"
  echo "${dir}"
}

paper_python_bin() {
  examples_python_bin "${REPO_ROOT}"
}

paper_include_neural() {
  [ "${LIDMAS_INCLUDE_NEURAL:-0}" = "1" ]
}

paper_neural_model_path() {
  local default_path="${REPO_ROOT}/examples/decoder_comparison/trained_model.json"
  echo "${LIDMAS_NEURAL_MODEL:-${default_path}}"
}
