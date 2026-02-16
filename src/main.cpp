#include <iostream>
#include "core/BinaryMatrix.h"
#include "decoders/BeliefPropagation.h"
#include "sim/MonteCarlo.h"

int main() {

    std::cout << "LiDMaS+ Monte Carlo Engine\n";

    // ----- Example: small (3 x 5) parity-check matrix -----
    BinaryMatrix H(3, 5);

    H.set(0,0,1); H.set(0,1,1);
    H.set(1,1,1); H.set(1,2,1);
    H.set(2,3,1); H.set(2,4,1);

    // ----- Decoder -----
    BeliefPropagation bp(H, 20, 0.5);

    // ----- Channel parameters -----
    channel::ChannelParams ch;
    ch.p_flip = 0.05;
    ch.p_erasure = 0.10;

    // ----- Run Monte Carlo -----
    TrialStats stats = run_monte_carlo(
        H,
        bp,
        5,          // number of bits
        1000,       // number of trials
        ch,
        42          // seed
    );

    std::cout << "Trials: " << stats.n_trials << "\n";
    std::cout << "Success rate: " << stats.success_rate << "\n";
    std::cout << "Avg iterations: " << stats.avg_iters << "\n";

    return 0;
}