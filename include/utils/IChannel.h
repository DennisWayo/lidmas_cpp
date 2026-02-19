#pragma once

#include <random>
#include <vector>

struct ChannelSample {
    std::vector<int> received_bits;
    std::vector<int> erasures;
};

class IChannel {
public:
    virtual ~IChannel() = default;
    virtual ChannelSample sample(std::mt19937& rng, int n, double p) = 0;
};
