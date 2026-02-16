#pragma once

#include <vector>
#include <random>

namespace channel {

    struct ChannelParams {
        double p_flip = 0.0;
        double p_erasure = 0.0;
    };

    std::vector<int> bsc_flip(
        const std::vector<int>& x,
        double p,
        std::mt19937& rng
    );

    std::vector<double> bsc_llr(
        const std::vector<int>& y,
        double p
    );

}