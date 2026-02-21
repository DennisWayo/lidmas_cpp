#pragma once

#include <cstdint>
#include <limits>
#include <string>
#include <vector>

struct SweepPoint {
    int d = 0;
    double p = 0.0;
    int trials = 0;
    double ler = 0.0;
    double ci_low = 0.0;
    double ci_high = 0.0;
};

struct CrossingEstimate {
    int d1 = 0;
    int d2 = 0;
    double pc = 0.0;
    double pc_low = 0.0;
    double pc_high = 0.0;
    double quality = 0.0; // [0,1] heuristic
};

struct CollapseFitResult {
    double pc = 0.0;
    double nu = 1.0;
    double cost = std::numeric_limits<double>::infinity();
    double pc_low = 0.0;
    double pc_high = 0.0;
    double nu_low = 1.0;
    double nu_high = 1.0;
    int bootstrap_samples = 0;
};

struct ScalingOutputs {
    std::vector<CrossingEstimate> crossings;
    CollapseFitResult collapse;
    std::string report_md;
    std::string summary_json;
};

class ScalingAnalysis {
public:
    static std::vector<CrossingEstimate>
    estimate_crossings(const std::vector<SweepPoint>& pts,
                       bool monotonic_smooth,
                       double ler_smooth_eps,
                       int min_pairs_required);

    static CollapseFitResult
    fit_collapse(const std::vector<SweepPoint>& pts,
                 bool monotonic_smooth,
                 double ler_smooth_eps,
                 double pc_init,
                 double nu_init,
                 double pc_min,
                 double pc_max,
                 double nu_min,
                 double nu_max,
                 int grid_pc,
                 int grid_nu,
                 int bootstrap_samples,
                 uint64_t seed);

    static ScalingOutputs
    run_all(const std::vector<SweepPoint>& pts,
            bool do_crossings,
            bool do_collapse,
            bool monotonic_smooth,
            double ler_smooth_eps,
            int bootstrap_samples,
            uint64_t seed);
};
