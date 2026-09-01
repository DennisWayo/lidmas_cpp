#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

PY_BIN="$(paper_python_bin)"
paper_prepare_plot_env

OUT_DIR="$(paper_results_dir "03_analysis")"
RUN_ROOT="${OUT_DIR}/runs"
mkdir -p "${RUN_ROOT}"

# Clear top-level stale analysis artifacts so 03_analysis stays canonical.
find "${OUT_DIR}" -maxdepth 1 -type f \( -name "table_*" -o -name "figure_*" -o -name "summary_*" -o -name "family_run_manifest.csv" \) -delete

FAMILIES_CSV="${LIDMAS_P4_CODE_FAMILIES:-surface,gkp}"
MANIFEST="${OUT_DIR}/family_run_manifest.csv"
echo "family,results_base,matrix_csv,delta_csv" > "${MANIFEST}"

_orig_results_base_set=0
_orig_code_family_set=0
_orig_results_base=""
_orig_code_family=""

if [ -n "${LIDMAS_P4_RESULTS_BASE+x}" ]; then
  _orig_results_base_set=1
  _orig_results_base="${LIDMAS_P4_RESULTS_BASE}"
fi
if [ -n "${LIDMAS_P4_CODE_FAMILY+x}" ]; then
  _orig_code_family_set=1
  _orig_code_family="${LIDMAS_P4_CODE_FAMILY}"
fi

restore_env() {
  if [ "${_orig_results_base_set}" -eq 1 ]; then
    export LIDMAS_P4_RESULTS_BASE="${_orig_results_base}"
  else
    unset LIDMAS_P4_RESULTS_BASE || true
  fi

  if [ "${_orig_code_family_set}" -eq 1 ]; then
    export LIDMAS_P4_CODE_FAMILY="${_orig_code_family}"
  else
    unset LIDMAS_P4_CODE_FAMILY || true
  fi
}
trap restore_env EXIT

IFS=',' read -r -a FAMILY_LIST <<< "${FAMILIES_CSV}"
for family_raw in "${FAMILY_LIST[@]}"; do
  family="${family_raw//[[:space:]]/}"
  [ -n "${family}" ] || continue
  case "${family}" in
    surface|gkp) ;;
    *)
      echo "Warning: unsupported code family '${family}', skipping." >&2
      continue
      ;;
  esac

  run_base="${RUN_ROOT}/${family}"
  mkdir -p "${run_base}"
  export LIDMAS_P4_RESULTS_BASE="${run_base}"
  export LIDMAS_P4_CODE_FAMILY="${family}"

  echo "paper_04 code-family run: ${family} -> ${run_base}"
  "${SCRIPT_DIR}/01_generate_comparison_requests.sh"
  "${SCRIPT_DIR}/02_replay_decoder_matrix.sh"
  "${SCRIPT_DIR}/03_analyze_comparison.sh"
  "${SCRIPT_DIR}/04_extended_analysis.sh"

  matrix_csv="${run_base}/03_analysis/table_replay_matrix.csv"
  delta_csv="${run_base}/04_extended_analysis/table_bootstrap_source_vs_reference.csv"
  echo "${family},${run_base},${matrix_csv},${delta_csv}" >> "${MANIFEST}"
done

"${PY_BIN}" "${SCRIPT_DIR}/scripts/analyze_code_family_trends.py" \
  --manifest "${MANIFEST}" \
  --out-dir "${OUT_DIR}"

"${PY_BIN}" "${SCRIPT_DIR}/scripts/compose_journal_results_figure.py" \
  --analysis-dir "${OUT_DIR}" \
  --out-prefix "${OUT_DIR}/figure_journal_results_summary" \
  --manuscript-dir "${OUT_DIR}/manuscript_figures" \
  --write-standalone

echo "paper_04 unified analysis complete: ${OUT_DIR}"
