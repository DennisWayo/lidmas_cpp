#pragma once

#include <vector>
#include <cmath>
#include "core/BinaryMatrix.h"

class BeliefPropagation {
private:
    const BinaryMatrix& H_;
    int max_iters_;
    double damping_;

    int last_iters_ = 0;

    std::vector<std::vector<int>> check_to_var_;
    std::vector<std::vector<int>> var_to_check_;

    void buildGraph_();
    double clamp(double x, double lo, double hi);

public:
    BeliefPropagation(const BinaryMatrix& H,
                      int max_iters,
                      double damping);

    std::vector<int> decodeErasureAware(
        const std::vector<int>& syndrome,
        const std::vector<int>& erasures,
        double p_error
    );

    int lastIterations() const { return last_iters_; }
};