#include "graph/TannerGraph.h"

TannerGraph::TannerGraph(const BinaryMatrix& H) {

    n_checks_ = H.rows();
    n_vars_   = H.cols();

    check_to_var_.resize(n_checks_);
    var_to_check_.resize(n_vars_);

    for (int c = 0; c < n_checks_; ++c) {
        for (int v = 0; v < n_vars_; ++v) {
            if (H.get(c, v) == 1) {
                check_to_var_[c].push_back(v);
                var_to_check_[v].push_back(c);
            }
        }
    }
}