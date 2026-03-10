#pragma once

#include <cstdint>
#include <string>
#include "core/BinaryMatrix.h"
#include "decoders/BeliefPropagation.h"
#include "qec/LogicalOperators.h"

enum class CSSNoiseMode {
    Pauli,
    Hybrid
};

struct CSSThresholdConfig {
    std::string decoder_name = "bp";
    CSSNoiseMode mode = CSSNoiseMode::Pauli;
    double p_start = 0.001;
    double p_end = 0.020;
    double p_step = 0.001;
    double sigma_start = 0.05;
    double sigma_end = 0.25;
    double sigma_step = 0.05;
    int trials = 2000;
    bool trials_explicit = false;
    uint64_t seed = 7300000;
    std::string out_csv = "css_threshold.csv";
    int min_trials = 200;
    int max_trials = 0; // resolved at runtime
    int batch_trials = 200;
    double target_ci_halfwidth = 0.01;
    double target_rel_ci = -1.0; // disabled when <= 0
    bool adaptive_enabled = false;
};

class CSSThresholdRunner {
public:
    static int run(const CSSThresholdConfig& cfg,
                   const BeliefPropagation::Params& bp_params,
                   const BinaryMatrix& hx,
                   const BinaryMatrix& hz,
                   const LogicalOperators& logicals);
};
