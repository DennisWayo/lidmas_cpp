#pragma once

#include <cstdint>

#include "WeightField.h"

class NeuralWeightField : public WeightField {
public:
    NeuralWeightField(int lattice_size, double noise_p = 0.0, uint64_t seed = 0, double alpha = 0.15);

    double edge_weight(int u, int v) const override;

private:
    int lattice_size_ = 0;
    double noise_p_ = 0.0;
    uint64_t seed_ = 0;
    double alpha_ = 0.15;

    static uint64_t mix64(uint64_t x);
};
