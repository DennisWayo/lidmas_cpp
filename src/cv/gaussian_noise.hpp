#pragma once

#include <cstdint>
#include <random>
#include <utility>

class GaussianNoise {
public:
    GaussianNoise(double sigma, uint64_t seed)
        : rng(seed), dist(0.0, sigma >= 0.0 ? sigma : -sigma) {}

    std::pair<double, double> sample() {
        return {dist(rng), dist(rng)};
    }

private:
    std::mt19937_64 rng;
    std::normal_distribution<double> dist;
};
