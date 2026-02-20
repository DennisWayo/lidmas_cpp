#include "LLRWeightField.h"

#include <algorithm>
#include <cmath>

namespace {

double clampProb(double p, double lo, double hi) {
    return std::clamp(p, lo, hi);
}

double llrFromProb(double p) {
    const double w = std::log((1.0 - p) / p);
    if (!std::isfinite(w)) return 0.0;
    return std::max(0.0, w);
}

} // namespace

LLRWeightField::LLRWeightField(double p_data,
                               double p_meas,
                               double p_idle,
                               double clamp_min,
                               double clamp_max)
    : p_data_(p_data),
      p_meas_(p_meas),
      p_idle_(p_idle),
      clamp_min_(std::max(1e-18, clamp_min)),
      clamp_max_(std::min(1.0 - 1e-18, clamp_max)) {
    if (clamp_min_ > clamp_max_) std::swap(clamp_min_, clamp_max_);
}

double LLRWeightField::edge_weight(int u, int v) const {
    // No explicit time dimension in current surface graph: default all non-self edges to data errors.
    // Self-edge is used as boundary/idle proxy where needed by decoder plugins.
    double p_e = p_data_;
    if (u == v) {
        p_e = p_idle_;
    }

    // Future-proof hook for time-like edges when time index is encoded in node IDs.
    if (u < 0 || v < 0) {
        p_e = p_meas_;
    }

    const double p = clampProb(p_e, clamp_min_, clamp_max_);
    return llrFromProb(p);
}
