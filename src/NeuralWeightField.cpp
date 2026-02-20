#include "NeuralWeightField.h"

#include <algorithm>
#include <cmath>

NeuralWeightField::NeuralWeightField(int lattice_size,
                                     double noise_p,
                                     uint64_t seed,
                                     double alpha)
    : lattice_size_(std::max(1, lattice_size)),
      noise_p_(std::clamp(noise_p, 0.0, 1.0)),
      seed_(seed),
      alpha_(std::max(0.0, alpha)) {}

uint64_t NeuralWeightField::mix64(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

double NeuralWeightField::edge_weight(int u, int v) const {
    if (u > v) std::swap(u, v);

    uint64_t h = seed_;
    h ^= mix64(static_cast<uint64_t>(u) + 0x9e3779b97f4a7c15ULL);
    h ^= mix64(static_cast<uint64_t>(v) + 0xbf58476d1ce4e5b9ULL);
    h ^= mix64(static_cast<uint64_t>(lattice_size_) + 0x94d049bb133111ebULL);
    const uint64_t p_key = static_cast<uint64_t>(std::llround(noise_p_ * 1e6));
    h ^= mix64(p_key + 0x27d4eb2f165667c5ULL);
    h = mix64(h);

    // 53-bit deterministic pseudo-random value in [0,1).
    const double rand01 = static_cast<double>((h >> 11) & ((1ULL << 53) - 1))
        * (1.0 / 9007199254740992.0);

    // Mock neural guidance: baseline 1.0 with bounded deterministic perturbation.
    const double weight = 1.0 + alpha_ * rand01;
    return std::max(1e-9, weight);
}
