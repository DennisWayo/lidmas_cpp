#pragma once

#include <vector>

struct LogicalPair {
    std::vector<int> LX;
    std::vector<int> LZ;
};

struct LogicalOperators {
    std::vector<std::vector<int>> LX;
    std::vector<std::vector<int>> LZ;

    bool empty() const { return LX.empty() && LZ.empty(); }
};

int dotMod2(const std::vector<int>& a,
            const std::vector<int>& b);

// residual Z errors anti-commuting with LX indicate a logical X flip.
bool hasLogicalXFailure(const std::vector<int>& residualZ,
                        const LogicalPair& L);

// residual X errors anti-commuting with LZ indicate a logical Z flip.
bool hasLogicalZFailure(const std::vector<int>& residualX,
                        const LogicalPair& L);

// Multi-logical variants (true if any logical flips).
bool hasLogicalXFailure(const std::vector<int>& residualZ,
                        const LogicalOperators& L);
bool hasLogicalZFailure(const std::vector<int>& residualX,
                        const LogicalOperators& L);

// Backward-compatible aliases used by v0.3/v0.4 code.
int dot_mod2(const std::vector<int>& a,
             const std::vector<int>& b);

std::vector<int> apply(
    const std::vector<std::vector<int>>& L,
    const std::vector<int>& e);
