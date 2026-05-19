#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

fail=0
tmp_hits="$(mktemp)"
trap 'rm -f "${tmp_hits}"' EXIT

echo "[guardrail] checking public docs for enterprise source paths..."
if grep -R -n -F "lidmas+/" docs README.md mkdocs.yml >"${tmp_hits}"; then
  echo "ERROR: enterprise source path reference found in public docs/config:"
  cat "${tmp_hits}"
  fail=1
fi

echo "[guardrail] checking pyproject sdist exclusions..."
if ! grep -F "sdist.exclude" pyproject.toml >/dev/null; then
  echo "ERROR: pyproject.toml is missing [tool.scikit-build] sdist.exclude guardrails."
  fail=1
fi
if ! grep -F "lidmas+/**" pyproject.toml >/dev/null; then
  echo "ERROR: pyproject.toml does not exclude enterprise app sources (lidmas+/**)."
  fail=1
fi

if [ "$#" -gt 0 ]; then
  for artifact in "$@"; do
    if [ ! -f "${artifact}" ]; then
      echo "ERROR: artifact not found: ${artifact}"
      fail=1
      continue
    fi

    case "${artifact}" in
      *.tar.gz)
        echo "[guardrail] inspecting sdist ${artifact}..."
        if tar -tzf "${artifact}" | grep -F "/lidmas+/" >/dev/null; then
          echo "ERROR: enterprise source leaked into sdist: ${artifact}"
          fail=1
        fi
        ;;
      *.whl)
        echo "[guardrail] inspecting wheel ${artifact}..."
        if python -m zipfile -l "${artifact}" | grep -F "lidmas+/" >/dev/null; then
          echo "ERROR: enterprise source leaked into wheel: ${artifact}"
          fail=1
        fi
        ;;
      *)
        echo "[guardrail] skipping unsupported artifact type: ${artifact}"
        ;;
    esac
  done
fi

if [ "${fail}" -ne 0 ]; then
  echo "[guardrail] FAILED"
  exit 1
fi

echo "[guardrail] OK"
