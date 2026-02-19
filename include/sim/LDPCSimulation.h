#pragma once

#include <functional>
#include <memory>
#include <utility>
#include <vector>
#include "core/BinaryMatrix.h"
#include "decoders/IDecoder.h"
#include "utils/IChannel.h"

struct LDPCPointStats {
    double ber = 0.0;
    double fer = 0.0;
    double avg_iter = 0.0;
    double parity_sat_rate = 0.0;
    double max_iter_hit_rate = 0.0;
};

class LDPCSimulation {
public:
    static LDPCPointStats run_point(
        const BinaryMatrix& H,
        const std::function<std::unique_ptr<IDecoder>()>& decoder_factory,
        IChannel& channel,
        int n,
        int trials,
        double p_error,
        int seed_base
    );

    static std::vector<std::pair<double, LDPCPointStats>> run_sweep(
        const BinaryMatrix& H,
        const std::function<std::unique_ptr<IDecoder>()>& decoder_factory,
        IChannel& channel,
        int n,
        int trials,
        double p_start,
        double p_end,
        double p_step,
        int seed_base
    );
};
