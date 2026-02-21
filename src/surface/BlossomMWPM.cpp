#include "surface/BlossomMWPM.h"

#include <algorithm>
#include <atomic>
#include <cstdlib>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <stdexcept>

namespace {

struct SolverState {
    const std::vector<std::vector<int>>* w = nullptr;
    std::vector<long long> memo;
    std::vector<int> choice;
    long long inf = std::numeric_limits<long long>::max() / 16;
    long long unknown = std::numeric_limits<long long>::min();
};

int firstSetBit(uint64_t mask) {
    for (int i = 0; i < 63; ++i) {
        if ((mask >> i) & 1ULL) return i;
    }
    return -1;
}

long long solveRec(uint64_t mask, SolverState& st) {
    if (mask == 0) return 0;
    const size_t idx = static_cast<size_t>(mask);
    if (st.memo[idx] != st.unknown) return st.memo[idx];

    const int i = firstSetBit(mask);
    const uint64_t mask_without_i = mask & ~(1ULL << i);

    long long best = st.inf;
    int best_j = -1;
    const int n = static_cast<int>(st.w->size());
    for (int j = i + 1; j < n; ++j) {
        if (((mask_without_i >> j) & 1ULL) == 0) continue;
        const uint64_t next = mask_without_i & ~(1ULL << j);
        const long long sub = solveRec(next, st);
        const int wij = (*st.w)[i][j];
        const long long cand = sub + static_cast<long long>(wij);
        if (cand < best) {
            best = cand;
            best_j = j;
        }
    }

    st.memo[idx] = best;
    st.choice[idx] = best_j;
    return best;
}

std::vector<int> solveGreedy(const std::vector<std::vector<int>>& weights) {
    const int n = static_cast<int>(weights.size());
    const int inf = std::numeric_limits<int>::max() / 16;
    std::vector<int> partner(n, -1);
    std::vector<unsigned char> used(static_cast<size_t>(n), 0);
    for (int matched = 0; matched < n; matched += 2) {
        int best_i = -1;
        int best_j = -1;
        int best_w = inf;
        for (int i = 0; i < n; ++i) {
            if (used[static_cast<size_t>(i)] != 0) continue;
            for (int j = i + 1; j < n; ++j) {
                if (used[static_cast<size_t>(j)] != 0) continue;
                const int wij = weights[i][j];
                if (wij < best_w || (wij == best_w && (best_i < 0 || i < best_i || (i == best_i && j < best_j)))) {
                    best_w = wij;
                    best_i = i;
                    best_j = j;
                }
            }
        }
        if (best_i < 0 || best_j < 0 || best_w >= inf) {
            throw std::invalid_argument("BlossomMWPM no feasible perfect matching (greedy)");
        }
        partner[best_i] = best_j;
        partner[best_j] = best_i;
        used[static_cast<size_t>(best_i)] = 1;
        used[static_cast<size_t>(best_j)] = 1;
    }
    return partner;
}

int configuredExactNodeLimit() {
    constexpr int kDefaultLimit = 24;
    constexpr int kHardMaxLimit = 24;
    int limit = kDefaultLimit;
    if (const char* raw = std::getenv("LIDMAS_MWPM_EXACT_MAX_NODES"); raw != nullptr && *raw != '\0') {
        try {
            limit = std::stoi(raw);
        } catch (...) {
            limit = kDefaultLimit;
        }
    }
    if ((limit & 1) != 0) limit -= 1;
    if (limit < 2) limit = 2;
    if (limit > kHardMaxLimit) limit = kHardMaxLimit;
    return limit;
}

int exactNodeLimit() {
    static const int limit = configuredExactNodeLimit();
    return limit;
}

void warnGreedyFallbackOnce(int n, int exact_limit) {
    static std::atomic<bool> warned{false};
    if (warned.exchange(true)) return;
    std::cerr << "WARNING: BlossomMWPM exact solver capped at n<=" << exact_limit
              << "; using greedy fallback for n=" << n
              << " (tune via LIDMAS_MWPM_EXACT_MAX_NODES)\n";
}

} // namespace

std::vector<int> BlossomMWPM::solve(const std::vector<std::vector<int>>& weights) {
    const int n = static_cast<int>(weights.size());
    if (n == 0) return {};
    if ((n & 1) != 0) {
        throw std::invalid_argument("BlossomMWPM requires even number of nodes");
    }
    if (n > 62) {
        throw std::invalid_argument("BlossomMWPM supports up to 62 nodes");
    }

    for (int i = 0; i < n; ++i) {
        if (static_cast<int>(weights[i].size()) != n) {
            throw std::invalid_argument("BlossomMWPM requires square weight matrix");
        }
        if (weights[i][i] != 0) {
            throw std::invalid_argument("BlossomMWPM requires zero diagonal");
        }
    }

    const int exact_limit = exactNodeLimit();
    if (n > exact_limit) {
        warnGreedyFallbackOnce(n, exact_limit);
        return solveGreedy(weights);
    }

    SolverState st;
    st.w = &weights;
    const uint64_t state_count = (1ULL << n);
    st.memo.assign(static_cast<size_t>(state_count), st.unknown);
    st.choice.assign(static_cast<size_t>(state_count), -1);
    const uint64_t full_mask = state_count - 1ULL;
    const long long opt = solveRec(full_mask, st);
    if (opt >= st.inf / 2) {
        throw std::invalid_argument("BlossomMWPM no feasible perfect matching");
    }

    std::vector<int> partner(n, -1);
    uint64_t mask = full_mask;
    while (mask != 0) {
        const int i = firstSetBit(mask);
        const int j = st.choice[static_cast<size_t>(mask)];
        if (i < 0 || j < 0) {
            throw std::invalid_argument("BlossomMWPM failed to reconstruct matching");
        }
        partner[i] = j;
        partner[j] = i;
        mask &= ~(1ULL << i);
        mask &= ~(1ULL << j);
    }
    return partner;
}
