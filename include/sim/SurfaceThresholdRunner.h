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
    std::string weight_mode = "uniform";
    bool uf_weighted = false;
    double llr_p_data = -1.0; // <0 => use sweep point p
    double llr_p_meas = -1.0; // <0 => use sweep point p
    double llr_p_idle = -1.0; // <0 => use sweep point p
    double llr_clamp_min = 1e-12;
    double llr_clamp_max = 1.0 - 1e-12;
    double mwpm_weight_scale = 1000.0;
    std::string mwpm_graph = "full";
    std::string neural_weights_path;
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
    int scaling_bootstrap = 200;
    uint64_t scaling_seed = 12345;
    bool pc_min_set = false;
    bool pc_max_set = false;
    bool nu_min_set = false;
    bool nu_max_set = false;
    double pc_min = 0.0;
    double pc_max = 0.0;
    double nu_min = 0.5;
    double nu_max = 3.0;
    int grid_pc = 61;
    int grid_nu = 51;
    double ler_smooth_eps = 0.0;
    std::string scaling_report = "surface_scaling_report.md";
    std::string scaling_json = "surface_scaling_summary.json";
};

class SurfaceThresholdRunner {
public:
    static int run(const SurfaceThresholdConfig& cfg);
    static int run(const SurfaceThresholdConfig& cfg, const PluginRegistry& reg);
};
