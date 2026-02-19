#pragma once

#include <vector>
#include "surface/SyndromeGraph.h"

class MatchingProblem {
public:
    using Node = SyndromeGraph::Node;

    void buildFromSyndromeGraph(const SyndromeGraph& g);

    int numDefects() const;
    const std::vector<Node>& defects() const;
    int pairWeight(int i, int j) const;
    int boundaryWeight(int i) const;

private:
    std::vector<Node> defects_;
    std::vector<std::vector<int>> pair_weights_;
    std::vector<int> boundary_weights_;
};
