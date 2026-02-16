#include "sim/MonteCarlo.h"
#include <random>

static inline int mod2(int x) { return x & 1; }

TrialStats run_monte_carlo(
    const BinaryMatrix& H,
    BeliefPropagation& bp,
    int n,
    int trials,
    const channel::ChannelParams ch,
    uint64_t seed
)
{
    std::mt19937_64 rng(seed);
    std::bernoulli_distribution flip_dist(ch.p_flip);
    std::bernoulli_distribution era_dist(ch.p_erasure);

    TrialStats out;
    out.n_trials = trials;

    long long it_sum = 0;

    for (int t = 0; t < trials; ++t) {

        std::vector<int> e_true(n, 0);
        std::vector<int> erasures(n, 0);

        for (int i = 0; i < n; ++i) {
            bool erased = era_dist(rng);
            erasures[i] = erased ? 1 : 0;

            if (!erased)
                e_true[i] = flip_dist(rng) ? 1 : 0;
        }

        std::vector<int> s = H.multiply(e_true);
        for (auto& v : s) v &= 1;

        std::vector<int> e_hat =
            bp.decodeErasureAware(s, erasures, ch.p_flip);

        std::vector<int> s_hat = H.multiply(e_hat);
        for (auto& v : s_hat) v &= 1;

        bool ok = (s_hat == s);

        if (ok) out.n_success++;
        else out.n_fail++;

        it_sum += bp.lastIterations();
    }

    out.success_rate =
        (trials > 0) ? double(out.n_success) / double(trials) : 0.0;

    out.avg_iters =
        (trials > 0) ? double(it_sum) / double(trials) : 0.0;

    return out;
}