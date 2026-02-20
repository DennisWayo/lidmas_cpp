#pragma once

#include <cstdint>
#include <string>
#include <vector>

class PluginRegistry;

struct SurfaceThresholdConfig {
    std::string decoder_name = "mwpm";
    std::vector<int> distances{3, 5, 7};
    double p_start = 0.01;
    double p_end = 0.15;
    double p_step = 0.01;
    int trials = 2000;
    bool trials_explicit = false;
    uint64_t seed = 12345;
    std::string out_csv = "surface_threshold.csv";
    bool monotonic_smooth = false;
    std::string neural_model_path;
    int min_trials = 200;
    int max_trials = 0; // resolved at runtime
    double target_ci_halfwidth = 0.01;
    double target_rel_ci = -1.0; // disabled when <= 0
    int batch_trials = 200;
    bool adaptive_enabled = false;
    bool auto_threshold = false;
    bool estimate_threshold = false;
    bool scaling_fit = false;
    int threads = 0; // <=0: use OpenMP runtime/environment default
};

class SurfaceThresholdRunner {
public:
    static int run(const SurfaceThresholdConfig& cfg);
    static int run(const SurfaceThresholdConfig& cfg, const PluginRegistry& reg);
};
