#pragma once

#include <vector>
#include "core/BinaryMatrix.h"
#include "graph/TannerGraph.h"
#include "decoders/BeliefPropagation.h"

struct CSSDecodeResult {
    std::vector<int> ex_hat;
    std::vector<int> ez_hat;
    std::vector<int> x_corrected;
    std::vector<int> z_corrected;
    // Concatenated [x_corrected | z_corrected]
    std::vector<int> corrected_codeword;
};

class CSSDecoder {
public:
    CSSDecoder(const BinaryMatrix& hx,
               const BinaryMatrix& hz,
               BeliefPropagation::Params x_params = {},
               BeliefPropagation::Params z_params = {});

    CSSDecodeResult decode(
        const std::vector<int>& sx,
        const std::vector<int>& sz,
        const std::vector<int>& rx,
        const std::vector<int>& rz,
        const std::vector<int>& erasures,
        double px,
        double pz);

private:
    TannerGraph gx_;
    TannerGraph gz_;
    BeliefPropagation bpx_;
    BeliefPropagation bpz_;
};
