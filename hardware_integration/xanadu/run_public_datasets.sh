#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${SCRIPT_DIR}/run_aurora.sh"
bash "${SCRIPT_DIR}/run_qca.sh"
bash "${SCRIPT_DIR}/run_gkp.sh"

echo "All public dataset example conversions completed."
