#pragma once

#include <string>

namespace lidmas_v07 {

class NeuralWeightModel {
public:
    bool load(const std::string& path);
    double edge_weight(int qubit_index, int distance, double p) const;

    bool enabled() const { return enabled_; }

private:
    bool enabled_ = false;
    double bias_ = 0.0;
    double w_qubit_ = 0.0;
    double w_distance_ = 0.0;
    double w_p_ = 0.0;
    double clamp_lo_ = -5.0;
    double clamp_hi_ = 5.0;
};

} // namespace lidmas_v07
