#pragma once

#include "core/BinaryMatrix.h"
#include <vector>

class TannerGraph {
private:
    int n_vars_;
    int n_checks_;

    std::vector<std::vector<int>> check_to_var_;
    std::vector<std::vector<int>> var_to_check_;

public:
    TannerGraph(const BinaryMatrix& H);

    int nVars() const { return n_vars_; }
    int nChecks() const { return n_checks_; }

    const std::vector<int>& checkNeighbors(int c) const {
        return check_to_var_[c];
    }

    const std::vector<int>& varNeighbors(int v) const {
        return var_to_check_[v];
    }
};