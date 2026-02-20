#pragma once

#include "WeightField.h"

class LLRWeightField : public WeightField {
public:
    LLRWeightField(double p_data,
                   double p_meas,
                   double p_idle,
                   double clamp_min = 1e-12,
                   double clamp_max = 1.0 - 1e-12);

    double edge_weight(int u, int v) const override;

private:
    double p_data_ = 0.01;
    double p_meas_ = 0.01;
    double p_idle_ = 0.01;
    double clamp_min_ = 1e-12;
    double clamp_max_ = 1.0 - 1e-12;
};
