#include "qec/LogicalOperators.h"
#include <stdexcept>

int dotMod2(const std::vector<int>& a,
            const std::vector<int>& b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("dotMod2 requires vectors of equal length");
    }

    int parity = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        parity ^= ((a[i] & 1) & (b[i] & 1));
    }
    return parity & 1;
}

bool hasLogicalXFailure(const std::vector<int>& residualZ,
                        const LogicalPair& L) {
    LogicalOperators ops;
    ops.LX = {L.LX};
    ops.LZ = {L.LZ};
    return hasLogicalXFailure(residualZ, ops);
}

bool hasLogicalZFailure(const std::vector<int>& residualX,
                        const LogicalPair& L) {
    LogicalOperators ops;
    ops.LX = {L.LX};
    ops.LZ = {L.LZ};
    return hasLogicalZFailure(residualX, ops);
}

bool hasLogicalXFailure(const std::vector<int>& residualZ,
                        const LogicalOperators& L) {
    if (L.LX.empty()) return false;
    const std::vector<int> flips = apply(L.LX, residualZ);
    for (int v : flips) {
        if ((v & 1) != 0) return true;
    }
    return false;
}

bool hasLogicalZFailure(const std::vector<int>& residualX,
                        const LogicalOperators& L) {
    if (L.LZ.empty()) return false;
    const std::vector<int> flips = apply(L.LZ, residualX);
    for (int v : flips) {
        if ((v & 1) != 0) return true;
    }
    return false;
}

int dot_mod2(const std::vector<int>& a,
             const std::vector<int>& b) {
    return dotMod2(a, b);
}

std::vector<int> apply(
    const std::vector<std::vector<int>>& L,
    const std::vector<int>& e) {
    std::vector<int> out;
    out.reserve(L.size());
    for (const auto& row : L) {
        out.push_back(dotMod2(row, e));
    }
    return out;
}
