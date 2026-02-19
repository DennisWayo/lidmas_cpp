#include "surface/MatchingProblem.h"

#include <stdexcept>

void MatchingProblem::buildFromSyndromeGraph(const SyndromeGraph& g) {
    defects_ = g.nodes();
    const int n = static_cast<int>(defects_.size());

    pair_weights_.assign(n, std::vector<int>(n, 0));
    boundary_weights_.assign(n, 0);

    for (int i = 0; i < n; ++i) {
        boundary_weights_[i] = g.nearestBoundaryDistance(i);
        for (int j = i + 1; j < n; ++j) {
            const int w = g.distance(i, j);
            pair_weights_[i][j] = w;
            pair_weights_[j][i] = w;
        }
    }
}

int MatchingProblem::numDefects() const {
    return static_cast<int>(defects_.size());
}

const std::vector<MatchingProblem::Node>& MatchingProblem::defects() const {
    return defects_;
}

int MatchingProblem::pairWeight(int i, int j) const {
    if (i < 0 || j < 0 || i >= numDefects() || j >= numDefects()) {
        throw std::out_of_range("MatchingProblem::pairWeight index out of range");
    }
    return pair_weights_[i][j];
}

int MatchingProblem::boundaryWeight(int i) const {
    if (i < 0 || i >= numDefects()) {
        throw std::out_of_range("MatchingProblem::boundaryWeight index out of range");
    }
    return boundary_weights_[i];
}
