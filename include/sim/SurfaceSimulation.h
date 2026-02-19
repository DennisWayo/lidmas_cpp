#pragma once

#include <cstdint>
#include <string>
#include <vector>

struct SurfaceStubSweepConfig {
    int d = 3;
    int trials = 200;
    uint64_t seed_base = 8400000;
    std::vector<double> p_values;
    std::string decoder_name = "mwpm_stub";
};

struct SurfaceStubPointStats {
    double p = 0.0;
    double defect_count_avg = 0.0;
    double correction_weight_avg = 0.0;
    double logical_fail_rate = 0.0;
};

class SurfaceSimulation {
public:
    static std::vector<SurfaceStubPointStats> run_stub_sweep(const SurfaceStubSweepConfig& cfg);
    static std::vector<SurfaceStubPointStats> run_mwpm_sweep(const SurfaceStubSweepConfig& cfg);
};
