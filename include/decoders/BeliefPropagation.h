#pragma once
#include <vector>
#include "graph/TannerGraph.h"

class BeliefPropagation {
public:
    enum class Mode {
        SUM_PRODUCT,
        NORMALIZED_MIN_SUM
    };

    struct Params {
        int max_iters = 50;
        double damping = 0.0;
        Mode mode = Mode::SUM_PRODUCT;
        double alpha = 0.8;
        double llr_max = 50.0;
        double convergence_tol = 1e-6;
        bool log_iteration_stats = false;
        bool log_llr_breakdown = false;
        int llr_breakdown_vars = 3;
        bool log_edge_debug = false;
        int edge_debug_var = 0;
    };

    struct DecodeResult {
        std::vector<int> estimate;
        bool syndrome_satisfied = false;
        bool hit_max_iters = false;
        int iterations = 0;
        double final_satisfied_fraction = 0.0;
    };

    BeliefPropagation(const TannerGraph& graph, Params params);

    // Core BP routine on precomputed channel LLRs.
    // Channel modeling (BSC, erasure-aware priors, etc.) stays in wrappers.
    DecodeResult decodeFromLLR(
        const std::vector<int>& syndrome,
        const std::vector<double>& channel_llr,
        const std::vector<int>& erasures
    );

    // (A) Channel decode: uses received bits (BSC-style)
    std::vector<int> decode(
        const std::vector<int>& syndrome,
        const std::vector<int>& received,
        const std::vector<int>& erasures,
        double p_error
    );

    // (B) Syndrome-only decode: QEC-style (no received bits)
    std::vector<int> decode(
        const std::vector<int>& syndrome,
        const std::vector<int>& erasures,
        double p_error
    );

    int lastIterations() const { return last_iters_; }
    bool lastHitMaxIters() const { return last_hit_max_iters_; }
    const std::vector<double>& lastSatisfiedCheckFractions() const {
        return last_satisfied_check_fractions_;
    }

private:
    const TannerGraph& graph_;
    Params params_;
    int last_iters_ = 0;
    bool last_hit_max_iters_ = false;
    std::vector<double> last_satisfied_check_fractions_;
};
