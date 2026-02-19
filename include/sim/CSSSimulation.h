#pragma once

#include <vector>
#include "qec/LogicalOperators.h"
#include "qec/QuantumCSSSimulator.h"

struct CSSDemoPointStats {
    double p = 0.0;
    double ler_total = 0.0;
    double ler_x = 0.0;
    double ler_z = 0.0;
    double avg_iter_x = 0.0;
    double avg_iter_z = 0.0;
};

class CSSSimulation {
public:
    static CSSDemoPointStats run_point(QuantumCSSSimulator& sim,
                                       double p,
                                       int trials,
                                       uint64_t seed_base,
                                       const LogicalPair* logicals);

    static std::vector<CSSDemoPointStats> run_css_demo(QuantumCSSSimulator& sim,
                                                        const std::vector<double>& p_values,
                                                        int trials,
                                                        uint64_t seed_base,
                                                        const LogicalPair* logicals);
};
