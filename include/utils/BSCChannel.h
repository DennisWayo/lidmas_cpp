#pragma once

#include "utils/IChannel.h"

class BSCChannel : public IChannel {
public:
    ChannelSample sample(std::mt19937& rng, int n, double p) override;
};
