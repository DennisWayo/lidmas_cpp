#pragma once

#include "core/BinaryMatrix.h"
#include "decoders/BeliefPropagation.h"
#include "utils/Channel.h"

struct TrialStats {
    int n_trials = 0;
    int n_success = 0;
    int n_fail = 0;
    double success_rate = 0.0;
    double avg_iters = 0.0;
};

TrialStats run_monte_carlo(
    const BinaryMatrix& H,
    BeliefPropagation& bp,
    int n,
    int trials,
    const channel::ChannelParams ch,
    uint64_t seed
);