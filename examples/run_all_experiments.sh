#!/bin/bash

# Stop execution immediately if any command fails
set -e

echo "=== Starting execution of all examples ==="

echo "-> Running: quick_smoke"
bash ./examples/quick_smoke/run.sh

echo "-> Running: plot_only"
bash ./examples/plot_only/run.sh

echo "-> Running: pauli_threshold"
bash ./examples/pauli_threshold/run.sh

echo "-> Running: adaptive_ci"
bash ./examples/adaptive_ci/run.sh

echo "-> Running: scaling_fit"
bash ./examples/scaling_fit/run.sh

echo "-> Running: hybrid_threshold"
bash ./examples/hybrid_threshold/run.sh

echo "-> Running: decoder_comparison"
bash ./examples/decoder_comparison/run.sh

echo "-> Running: failure_debug"
bash ./examples/failure_debug/run.sh

echo "-> Running: cv_demo"
bash ./examples/cv_demo/run.sh

echo "-> Running: reproducibility_seed"
bash ./examples/reproducibility_seed/run.sh

echo "=== All examples executed successfully! ==="