#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include "decoders/BeliefPropagation.h"

class PluginRegistry;

enum class NoiseMode {
    Pauli,
    Hybrid,
    GKP
};

struct SurfaceThresholdConfig {
    std::string decoder_name = "mwpm";
    NoiseMode mode = NoiseMode::Pauli;
    double cv_sigma = 0.0;
    double sigma_start = 0.05;
    double sigma_end = 0.60;
    double sigma_step = 0.05;
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
    double gkp_gate_error = 0.0;
    double gkp_meas_error = 0.0;
    double gkp_idle_error = 0.0;
    double gkp_loss_prob = 0.0;
    std::vector<double> gkp_loss_map;
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
    bool use_gpu = false;
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
    BeliefPropagation::Mode bp_mode = BeliefPropagation::Mode::SUM_PRODUCT;
    double bp_alpha = 0.8;
};

class SurfaceThresholdRunner {
public:
    static int run(const SurfaceThresholdConfig& cfg);
    static int run(const SurfaceThresholdConfig& cfg, const PluginRegistry& reg);
};
