#pragma once

#include <random>
#include <vector>

enum class QECNoiseModel {
    INDEPENDENT_XZ,
    DEPOLARIZING
};

struct QECSample {
    std::vector<int> eX;
    std::vector<int> eZ;
};

class IQECChannel {
public:
    virtual ~IQECChannel() = default;
    virtual QECSample sample(std::mt19937& rng,
                             int n,
                             QECNoiseModel model,
                             double pX,
                             double pZ,
                             double p) = 0;
};
