#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${REPO_ROOT}/examples/common.sh"

paper_results_dir() {
  local name="$1"
  local base="${LIDMAS_P5_RESULTS_BASE:-${REPO_ROOT}/examples/paper_runs/paper_05/results}"
  local dir="${base}/${name}"
  mkdir -p "${dir}"
  echo "${dir}"
}

paper_python_bin() {
  examples_python_bin "${REPO_ROOT}"
}

paper_prepare_plot_env() {
  local cache_root="${REPO_ROOT}/.cache"
  local home_root="${cache_root}/home"
  local xdg_cache="${home_root}/.cache"
  local mpl_cache="${cache_root}/matplotlib"

  mkdir -p "${xdg_cache}/fontconfig" "${home_root}/.matplotlib" "${mpl_cache}"

  export HOME="${home_root}"
  export XDG_CACHE_HOME="${xdg_cache}"
  export MPLCONFIGDIR="${mpl_cache}"
  export MPLBACKEND="Agg"
}
