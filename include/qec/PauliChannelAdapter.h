#pragma once

#include "qec/IQECChannel.h"

class PauliChannelAdapter : public IQECChannel {
public:
    QECSample sample(std::mt19937& rng,
                     int n,
                     QECNoiseModel model,
                     double pX,
                     double pZ,
                     double p) override;
};
