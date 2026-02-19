#pragma once

#include <cmath>
#include <cstdint>

inline int ldpc_p_key(double p_error) {
    return static_cast<int>(std::llround(p_error * 1000000.0));
}

inline int ldpc_trial_seed(int seed_base, int n, int p_key, int t) {
    return seed_base + n * 10000 + p_key + t;
}

inline int ldpc_debug_seed(double p_error, int n) {
    return 700000 + static_cast<int>(p_error * 1000.0) + n;
}

inline int qec_p_key_independent(double pX, double pZ) {
    return static_cast<int>(std::llround(pX * 1e6) + 17.0 * std::llround(pZ * 1e6));
}

inline int qec_p_key_depolarizing(double p) {
    return static_cast<int>(std::llround(p * 1e6));
}

inline uint32_t qec_trial_seed(uint64_t seed_base, int p_key, int t) {
    return static_cast<uint32_t>(seed_base + p_key + t);
}
