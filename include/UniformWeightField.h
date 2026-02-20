#pragma once

#include "WeightField.h"

class UniformWeightField : public WeightField {
public:
    double edge_weight(int u, int v) const override;
};
