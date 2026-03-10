#include "qec/PauliChannelAdapter.h"
#include "qec/PauliChannel.h"

QECSample PauliChannelAdapter::sample(std::mt19937& rng,
                                      int n,
                                      QECNoiseModel model,
                                      double pX,
                                      double pZ,
                                      double p) {
    PauliSample raw;
    if (model == QECNoiseModel::DEPOLARIZING) {
        raw = PauliChannel::sampleDepolarizing(n, p, rng);
    } else if (model == QECNoiseModel::HYBRID_GKP) {
        // In hybrid mode, the scalar parameter `p` carries sigma.
        raw = PauliChannel::sampleHybridGKP(n, p, rng);
    } else {
        raw = PauliChannel::sampleIndependentXZ(n, pX, pZ, rng);
    }

    QECSample out;
    out.eX = std::move(raw.eX);
    out.eZ = std::move(raw.eZ);
    return out;
}
