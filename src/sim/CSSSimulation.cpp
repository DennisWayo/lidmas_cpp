#include "sim/CSSSimulation.h"

CSSDemoPointStats CSSSimulation::run_point(QuantumCSSSimulator& sim,
                                           double sweep_value,
                                           int trials,
                                           uint64_t seed_base,
                                           const LogicalOperators* logicals,
                                           QECNoiseModel noise_model) {
    QuantumCSSSimulator::RunConfig cfg;
    cfg.trials = trials;
    cfg.seed_base = seed_base;
    cfg.noise_model = noise_model;
    if (noise_model == QECNoiseModel::DEPOLARIZING || noise_model == QECNoiseModel::HYBRID_GKP) {
        cfg.p = sweep_value;
    } else {
        cfg.pX = sweep_value;
        cfg.pZ = sweep_value;
    }

    const auto s = sim.run(cfg, logicals);

    CSSDemoPointStats out;
    out.p = sweep_value;
    out.ler_total = s.logical_total_fail_rate;
    out.ler_x = s.logical_X_fail_rate;
    out.ler_z = s.logical_Z_fail_rate;
    out.avg_iter_x = s.avg_iter_X;
    out.avg_iter_z = s.avg_iter_Z;
    return out;
}

std::vector<CSSDemoPointStats> CSSSimulation::run_css_demo(QuantumCSSSimulator& sim,
                                                           const std::vector<double>& sweep_values,
                                                           int trials,
                                                           uint64_t seed_base,
                                                           const LogicalOperators* logicals,
                                                           QECNoiseModel noise_model) {
    std::vector<CSSDemoPointStats> out;
    out.reserve(sweep_values.size());
    for (double v : sweep_values) {
        out.push_back(run_point(sim, v, trials, seed_base, logicals, noise_model));
    }
    return out;
}
