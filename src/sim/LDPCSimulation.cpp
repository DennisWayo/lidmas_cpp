#include "sim/LDPCSimulation.h"
#include "utils/SeedUtils.h"
#include "utils/SyndromeUtils.h"
#include <random>

#ifdef _OPENMP
#include <omp.h>
#endif

LDPCPointStats LDPCSimulation::run_point(
    const BinaryMatrix& H,
    const std::function<std::unique_ptr<IDecoder>()>& decoder_factory,
    IChannel& channel,
    int n,
    int trials,
    double p_error,
    int seed_base
) {
    long long frame_errors = 0;
    long long bit_errors = 0;
    long long it_sum = 0;
    long long parity_sat = 0;
    long long max_iter_hits = 0;

    const int p_key = ldpc_p_key(p_error);
    const std::vector<int> syndrome = zero_syndrome(H.rows());

    #pragma omp parallel for reduction(+:frame_errors,bit_errors,it_sum,parity_sat,max_iter_hits) schedule(static)
    for (int t = 0; t < trials; ++t) {
        std::mt19937 rng(ldpc_trial_seed(seed_base, n, p_key, t));
        const ChannelSample sample = channel.sample(rng, n, p_error);

        auto decoder = decoder_factory();
        DecodeRequest req;
        req.syndrome = &syndrome;
        req.received_bits = &sample.received_bits;
        req.erasures = &sample.erasures;
        req.p_error = p_error;

        const DecodeResult dec = decoder->decode(req);
        const std::vector<int>& x_hat = dec.correction;

        int frame_bit_errors = 0;
        for (int bit : x_hat)
            frame_bit_errors += (bit & 1);
        bit_errors += frame_bit_errors;
        if (frame_bit_errors > 0)
            frame_errors++;

        it_sum += dec.iters;
        if (dec.hit_max_iters)
            max_iter_hits++;

        if (parity_satisfied(H, x_hat))
            parity_sat++;
    }

    LDPCPointStats out;
    out.ber = static_cast<double>(bit_errors) / static_cast<double>(trials * n);
    out.fer = static_cast<double>(frame_errors) / static_cast<double>(trials);
    out.avg_iter = static_cast<double>(it_sum) / static_cast<double>(trials);
    out.parity_sat_rate = static_cast<double>(parity_sat) / static_cast<double>(trials);
    out.max_iter_hit_rate = static_cast<double>(max_iter_hits) / static_cast<double>(trials);
    return out;
}

std::vector<std::pair<double, LDPCPointStats>> LDPCSimulation::run_sweep(
    const BinaryMatrix& H,
    const std::function<std::unique_ptr<IDecoder>()>& decoder_factory,
    IChannel& channel,
    int n,
    int trials,
    double p_start,
    double p_end,
    double p_step,
    int seed_base
) {
    std::vector<std::pair<double, LDPCPointStats>> out;
    for (double p = p_start; p <= p_end + 1e-12; p += p_step) {
        out.push_back({p, run_point(H, decoder_factory, channel, n, trials, p, seed_base)});
    }
    return out;
}
