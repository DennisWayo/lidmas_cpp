#pragma once

#include <cstdint>
#include <string>

#include "decoders/BeliefPropagation.h"

struct SmokeConfig {
    int distance = 3;
    double p = 0.02;
    int trials = 50;
    uint64_t seed = 1337;
    std::string decoder_name = "mwpm";
    std::string mode = "pauli";
    std::string weight_mode = "uniform";
};

bool run_self_tests(const BeliefPropagation::Params& params);
bool run_smoke_tests(const SmokeConfig& cfg);
