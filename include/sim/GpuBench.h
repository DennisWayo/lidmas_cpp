#pragma once

#include <cstdint>

int run_gpu_bench(int d, int trials, int batch_trials, double p, uint64_t seed);
