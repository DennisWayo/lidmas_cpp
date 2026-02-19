#include "sim/CSSSimulation.h"

CSSDemoPointStats CSSSimulation::run_point(QuantumCSSSimulator& sim,
                                           double p,
                                           int trials,
                                           uint64_t seed_base,
                                           const LogicalPair* logicals) {
    QuantumCSSSimulator::RunConfig cfg;
    cfg.trials = trials;
    cfg.seed_base = seed_base;
    cfg.noise_model = QECNoiseModel::INDEPENDENT_XZ;
    cfg.pX = p;
    cfg.pZ = p;

    const auto s = sim.run(cfg, logicals);

    CSSDemoPointStats out;
    out.p = p;
    out.ler_total = s.logical_total_fail_rate;
    out.ler_x = s.logical_X_fail_rate;
    out.ler_z = s.logical_Z_fail_rate;
    out.avg_iter_x = s.avg_iter_X;
    out.avg_iter_z = s.avg_iter_Z;
    return out;
}

std::vector<CSSDemoPointStats> CSSSimulation::run_css_demo(QuantumCSSSimulator& sim,
                                                           const std::vector<double>& p_values,
                                                           int trials,
                                                           uint64_t seed_base,
                                                           const LogicalPair* logicals) {
    std::vector<CSSDemoPointStats> out;
    out.reserve(p_values.size());
    for (double p : p_values) {
        out.push_back(run_point(sim, p, trials, seed_base, logicals));
    }
    return out;
}
