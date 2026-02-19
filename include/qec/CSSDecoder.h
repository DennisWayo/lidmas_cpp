#pragma once

#include <vector>
#include "decoders/BeliefPropagation.h"
#include "qec/CSSCode.h"
#include "qec/CSSSyndrome.h"
#include "graph/TannerGraph.h"

struct CSSDecodeResult {
    std::vector<int> eX;
    std::vector<int> eZ;

    bool parity_sat_X = false;
    bool parity_sat_Z = false;

    bool has_logicals = false;

    std::vector<int> logical_flip_X;  // Lz · eX
    std::vector<int> logical_flip_Z;  // Lx · eZ
    bool logical_fail = false;

    int iters_X = 0;
    int iters_Z = 0;
    bool max_iter_hit_X = false;
    bool max_iter_hit_Z = false;
};

using BeliefPropagationParams = BeliefPropagation::Params;

class CSSDecoder {
public:
    CSSDecoder(const CSSCode& code,
               BeliefPropagationParams params = {});

    CSSDecodeResult decode(const CSSSyndrome& syndrome,
        double px,
        double pz,
        const std::vector<int>& erasures = {});

private:
    const CSSCode& code_;
    TannerGraph gx_;
    TannerGraph gz_;
    BeliefPropagation bpx_;
    BeliefPropagation bpz_;
};
