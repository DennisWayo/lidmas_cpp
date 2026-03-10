#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/01_pauli_baseline.sh"
"${SCRIPT_DIR}/02_hybrid_baseline.sh"
"${SCRIPT_DIR}/03_hybrid_multidistance.sh"
"${SCRIPT_DIR}/04_pauli_threshold.sh"
"${SCRIPT_DIR}/05_hybrid_threshold.sh"

echo "All paper runs complete."

