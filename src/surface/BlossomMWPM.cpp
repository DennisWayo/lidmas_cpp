#include "surface/BlossomMWPM.h"

#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_map>

namespace {

struct SolverState {
    const std::vector<std::vector<int>>* w = nullptr;
    std::unordered_map<uint64_t, long long> memo;
    std::unordered_map<uint64_t, int> choice;
    long long inf = std::numeric_limits<long long>::max() / 16;
};

int firstSetBit(uint64_t mask) {
    for (int i = 0; i < 63; ++i) {
        if ((mask >> i) & 1ULL) return i;
    }
    return -1;
}

long long solveRec(uint64_t mask, SolverState& st) {
    if (mask == 0) return 0;
    const auto it = st.memo.find(mask);
    if (it != st.memo.end()) return it->second;

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

    st.memo[mask] = best;
    st.choice[mask] = best_j;
    return best;
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

    SolverState st;
    st.w = &weights;
    const uint64_t full_mask = (n == 64) ? ~0ULL : ((1ULL << n) - 1ULL);
    const long long opt = solveRec(full_mask, st);
    if (opt >= st.inf / 2) {
        throw std::invalid_argument("BlossomMWPM no feasible perfect matching");
    }

    std::vector<int> partner(n, -1);
    uint64_t mask = full_mask;
    while (mask != 0) {
        const int i = firstSetBit(mask);
        const int j = st.choice[mask];
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
