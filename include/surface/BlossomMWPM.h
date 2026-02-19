#pragma once

#include <vector>

// In-repo minimum-weight perfect matching solver API used by surface MWPM decoder.
// The input is a symmetric complete-graph weight matrix with even size.
class BlossomMWPM {
public:
    // Returns partner index for each node in the matching.
    // Throws std::invalid_argument on malformed input.
    static std::vector<int> solve(const std::vector<std::vector<int>>& weights);
};
