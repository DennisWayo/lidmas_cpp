#!/bin/bash

set -euo pipefail

resolve_lidmas_binary() {
  local repo_root="$1"
  if [ -x "${repo_root}/lidmas" ]; then
    echo "${repo_root}/lidmas"
    return 0
  fi
  if [ -x "${repo_root}/build/lidmas" ]; then
    echo "${repo_root}/build/lidmas"
    return 0
  fi
  echo "Error: lidmas binary not found. Build first (e.g. cmake -S . -B build && cmake --build build -j)." >&2
  return 1
}

results_dir_for() {
  local repo_root="$1"
  local example_name="$2"
  local dir="${repo_root}/examples/results/${example_name}"
  mkdir -p "${dir}"
  echo "${dir}"
}

examples_python_bin() {
  local repo_root="$1"
  if [ -x "${repo_root}/.venv/bin/python" ]; then
    echo "${repo_root}/.venv/bin/python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  return 1
}

ensure_examples_env() {
  local repo_root="$1"
  local venv_dir="${repo_root}/.venv"
  local py_bin="${venv_dir}/bin/python"
  local req_file="${repo_root}/examples/requirements.txt"

  if [ "${LIDMAS_SKIP_PY_DEPS:-0}" = "1" ]; then
    echo "[examples] skipping Python dependency setup (LIDMAS_SKIP_PY_DEPS=1)"
    return 0
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found. Install Python 3 first." >&2
    return 1
  fi

  if [ ! -x "${py_bin}" ]; then
    echo "[examples] creating virtual environment at .venv"
    python3 -m venv "${venv_dir}"
  fi

  if ! "${py_bin}" -c "import pandas, matplotlib" >/dev/null 2>&1; then
    echo "[examples] installing Python dependencies from examples/requirements.txt"
    if ! "${py_bin}" -m pip install -r "${req_file}"; then
      cat >&2 <<'EOF'
Error: failed to install Python plotting dependencies.
- If your machine is online, retry: ./examples/setup_env.sh
- If you only want simulation CSV outputs, run with: LIDMAS_SKIP_PY_DEPS=1
- If matplotlib/pandas are already installed elsewhere, activate that env first.
EOF
      return 1
    fi
  fi
}

run_publication_plot() {
  local repo_root="$1"
  shift

  local py_bin
  if ! py_bin="$(examples_python_bin "${repo_root}")"; then
    echo "Warning: python3 not found; skipping publication figure generation." >&2
    return 0
  fi

  local plot_script="${repo_root}/examples/plot_only/publish_plot.py"
  if [ ! -f "${plot_script}" ]; then
    echo "Warning: ${plot_script} not found; skipping publication figure generation." >&2
    return 0
  fi

  local cache_root="${repo_root}/.cache"
  local home_root="${cache_root}/home"
  local xdg_cache="${home_root}/.cache"
  local mpl_cache="${cache_root}/matplotlib"
  mkdir -p "${xdg_cache}/fontconfig" "${home_root}/.matplotlib" "${mpl_cache}"

  if ! HOME="${home_root}" XDG_CACHE_HOME="${xdg_cache}" MPLCONFIGDIR="${mpl_cache}" MPLBACKEND=Agg \
    "${py_bin}" "${plot_script}" "$@"; then
    echo "Warning: publication figure generation failed. You can retry manually with:" >&2
    echo "  ${py_bin} ${plot_script} $*" >&2
    return 0
  fi
}
