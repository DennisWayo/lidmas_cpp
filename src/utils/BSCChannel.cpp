#include "utils/BSCChannel.h"
#include <algorithm>

ChannelSample BSCChannel::sample(std::mt19937& rng, int n, double p) {
    ChannelSample out;
    out.received_bits.assign(n, 0);
    out.erasures.assign(n, 0);

    std::bernoulli_distribution flip(std::clamp(p, 0.0, 1.0));
    for (int i = 0; i < n; ++i) {
        out.received_bits[i] = flip(rng) ? 1 : 0;
    }

    return out;
}
