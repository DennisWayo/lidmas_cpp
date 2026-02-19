#include "qec/LogicalOperators.h"
#include <stdexcept>

int dot_mod2(const std::vector<int>& a,
             const std::vector<int>& b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("dot_mod2 requires vectors of equal length");
    }

    int parity = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        parity ^= ((a[i] & 1) & (b[i] & 1));
    }
    return parity & 1;
}

std::vector<int> apply(
    const std::vector<std::vector<int>>& L,
    const std::vector<int>& e) {
    std::vector<int> out;
    out.reserve(L.size());
    for (const auto& row : L) {
        out.push_back(dot_mod2(row, e));
    }
    return out;
}
