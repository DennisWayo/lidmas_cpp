#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>

struct DecoderConfig {
    std::string decoder_name;
    int distance = 0;
    int trials = 0;
    uint64_t seed = 0;
    double p = 0.0;

    int max_iters = 80;
    double alpha = 0.8;
    double damping = 0.0;
    double llr_max = 50.0;
    double p_error = 0.0;

    std::unordered_map<std::string, int> int_params;
    std::unordered_map<std::string, double> double_params;
    std::unordered_map<std::string, std::string> string_params;
    std::unordered_map<std::string, const void*> ptr_params;
};
