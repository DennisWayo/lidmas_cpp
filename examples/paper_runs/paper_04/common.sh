#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${REPO_ROOT}/examples/common.sh"

paper_results_dir() {
  local name="$1"
  local base="${LIDMAS_P4_RESULTS_BASE:-${REPO_ROOT}/examples/paper_runs/paper_04/results}"
  local dir="${base}/${name}"
  mkdir -p "${dir}"
  echo "${dir}"
}

paper_python_bin() {
  examples_python_bin "${REPO_ROOT}"
}

paper_neural_model_path() {
  local default_path="${REPO_ROOT}/examples/decoder_comparison/trained_model.json"
  echo "${LIDMAS_NEURAL_MODEL:-${default_path}}"
}

paper_default_decoder_csv() {
  echo "mwpm,uf,bp,neural_mwpm"
}

paper_resolve_decoders() {
  local decoder_csv="${LIDMAS_DECODERS:-$(paper_default_decoder_csv)}"
  local neural_model
  neural_model="$(paper_neural_model_path)"

  local -a raw_decoders=()
  local -a resolved=()
  IFS=',' read -r -a raw_decoders <<< "${decoder_csv}"

  local decoder
  for decoder in "${raw_decoders[@]}"; do
    decoder="${decoder//[[:space:]]/}"
    [ -z "${decoder}" ] && continue
    case "${decoder}" in
      mwpm|uf|bp|stub)
        resolved+=("${decoder}")
        ;;
      neural_mwpm)
        if [ -f "${neural_model}" ]; then
          resolved+=("${decoder}")
        else
          echo "Warning: neural model not found at ${neural_model}; skipping neural_mwpm" >&2
        fi
        ;;
      *)
        echo "Warning: unsupported decoder '${decoder}'; skipping" >&2
        ;;
    esac
  done

  if [ "${#resolved[@]}" -eq 0 ]; then
    echo "Error: no valid decoders selected. Set LIDMAS_DECODERS (e.g. mwpm,uf,bp)." >&2
    return 1
  fi

  printf '%s\n' "${resolved[@]}"
}

paper_dataset_label_from_request_path() {
  local path="$1"
  local base
  base="$(basename "${path}")"
  base="${base%.ndjson}"
  base="${base#decoder_requests}"
  if [ -z "${base}" ]; then
    echo "job"
    return 0
  fi
  base="${base#_}"
  echo "${base}"
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
