#pragma once

#include <cstdint>
#include <string>
#include <vector>

class PluginRegistry;

struct SurfaceSweepConfig {
    int d = 3;
    int trials = 200;
    uint64_t seed_base = 8400000;
    std::vector<double> p_values;
    std::string decoder_name = "stub";
    std::string neural_model_path;
};

using SurfaceStubSweepConfig = SurfaceSweepConfig;

struct SurfaceStubPointStats {
    double p = 0.0;
    double defect_count_avg = 0.0;
    double correction_weight_avg = 0.0;
    double logical_fail_rate = 0.0;
    double avg_runtime_ms = 0.0;
};

class SurfaceSimulation {
public:
    static std::vector<SurfaceStubPointStats> run_decoder_sweep(const SurfaceSweepConfig& cfg);
    static std::vector<SurfaceStubPointStats> run_decoder_sweep(const SurfaceSweepConfig& cfg,
                                                                const PluginRegistry& reg);
    static std::vector<SurfaceStubPointStats> run_stub_sweep(const SurfaceSweepConfig& cfg);
    static std::vector<SurfaceStubPointStats> run_mwpm_sweep(const SurfaceSweepConfig& cfg);
};
