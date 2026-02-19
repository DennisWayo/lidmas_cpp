#include "qec/PauliChannelAdapter.h"
#include "qec/PauliChannel.h"

QECSample PauliChannelAdapter::sample(std::mt19937& rng,
                                      int n,
                                      QECNoiseModel model,
                                      double pX,
                                      double pZ,
                                      double p) {
    PauliSample raw = (model == QECNoiseModel::DEPOLARIZING)
        ? PauliChannel::sampleDepolarizing(n, p, rng)
        : PauliChannel::sampleIndependentXZ(n, pX, pZ, rng);

    QECSample out;
    out.eX = std::move(raw.eX);
    out.eZ = std::move(raw.eZ);
    return out;
}
