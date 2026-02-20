#pragma once

#include <string>

class NeuralWeightModel {
public:
    bool loadFromJson(const std::string& path);
    double predictScale(double manhattan, double dx, double dy, double near_boundary) const;

    bool enabled() const { return enabled_; }
    double clampLo() const { return clamp_lo_; }
    double clampHi() const { return clamp_hi_; }

private:
    bool enabled_ = false;
    std::string type_ = "linear";
    double bias_ = 1.0;
    double w_manhattan_ = 0.0;
    double w_dx_ = 0.0;
    double w_dy_ = 0.0;
    double w_near_boundary_ = 0.0;
    double clamp_lo_ = 0.5;
    double clamp_hi_ = 2.0;
};
