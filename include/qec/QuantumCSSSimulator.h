#pragma once

#include <cstdint>
#include <functional>
#include <memory>
#include <vector>
#include "core/BinaryMatrix.h"
#include "decoders/IDecoder.h"
#include "qec/IQECChannel.h"
#include "qec/LogicalOperators.h"

class QuantumCSSSimulator {
public:
    struct RunConfig {
        int trials = 200;
        uint64_t seed_base = 1234567;
        QECNoiseModel noise_model = QECNoiseModel::INDEPENDENT_XZ;
        double pX = 0.01;
        double pZ = 0.01;
        double p = 0.01;  // depolarizing probability
    };

    struct QECStats {
        double logical_X_fail_rate = 0.0;
        double logical_Z_fail_rate = 0.0;
        double logical_total_fail_rate = 0.0;
        double avg_iter_X = 0.0;
        double avg_iter_Z = 0.0;
        double max_iter_hit_rate_X = 0.0;
        double max_iter_hit_rate_Z = 0.0;
        double parity_sat_rate_X = 0.0;
        double parity_sat_rate_Z = 0.0;
    };

    QuantumCSSSimulator(const BinaryMatrix& Hx,
                        const BinaryMatrix& Hz,
                        const std::function<std::unique_ptr<IDecoder>()>& x_decoder_factory,
                        const std::function<std::unique_ptr<IDecoder>()>& z_decoder_factory,
                        IQECChannel& channel);

    QECStats run(const RunConfig& cfg,
                 const LogicalPair* logicals = nullptr) const;

private:
    BinaryMatrix hx_;
    BinaryMatrix hz_;
    std::function<std::unique_ptr<IDecoder>()> x_decoder_factory_;
    std::function<std::unique_ptr<IDecoder>()> z_decoder_factory_;
    IQECChannel& channel_;
};
