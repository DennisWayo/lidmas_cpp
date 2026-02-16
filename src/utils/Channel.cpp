#include "utils/Channel.h"
#include <cmath>
#include <stdexcept>

namespace channel {

    std::vector<int> bsc_flip(
        const std::vector<int>& x,
        double p,
        std::mt19937& rng
    ) {
        if (p < 0.0 || p > 1.0)
            throw std::invalid_argument("p must be in [0,1]");

        std::bernoulli_distribution flip(p);
        std::vector<int> y = x;

        for (auto& bit : y)
            bit ^= flip(rng) ? 1 : 0;

        return y;
    }

    std::vector<double> bsc_llr(
        const std::vector<int>& y,
        double p
    ) {
        if (p <= 0.0 || p >= 0.5)
            throw std::invalid_argument("p must be in (0,0.5)");

        const double L0 = std::log((1.0 - p) / p);
        std::vector<double> llr(y.size(), 0.0);

        for (size_t i = 0; i < y.size(); ++i)
            llr[i] = (y[i] == 0 ? +L0 : -L0);

        return llr;
    }

}