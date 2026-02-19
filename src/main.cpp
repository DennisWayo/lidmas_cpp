// ================================
// FILE: src/main.cpp
// LDPC + BSC + BP sweeps with diagnostics
// ================================

#include <iomanip>
#include <iostream>
#include <random>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>

#include "codes/LDPCGenerator.h"
#include "decoders/BeliefPropagation.h"
#include "graph/GraphDiagnostics.h"
#include "graph/TannerGraph.h"
#include "utils/CSVWriter.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

struct SweepConfig {
    int m = 0;
    int n = 0;
    int col_weight = 3;
    int trials = 200;
    double p_start = 0.02;
    double p_end = 0.15;
    double p_step = 0.01;
    std::string label;
    std::string csv_file;
};

struct RuntimeOptions {
    BeliefPropagation::Mode mode = BeliefPropagation::Mode::SUM_PRODUCT;
    double alpha = 0.8;
    bool log_decode_iterations = false;
};

struct PointStats {
    double ber = 0.0;
    double fer = 0.0;
    double avg_iter = 0.0;
    double parity_sat_rate = 0.0;
    double max_iter_hit_rate = 0.0;
};

RuntimeOptions parseOptions(int argc, char** argv) {
    RuntimeOptions opts;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--bp=sum-product") {
            opts.mode = BeliefPropagation::Mode::SUM_PRODUCT;
        } else if (arg == "--bp=nms") {
            opts.mode = BeliefPropagation::Mode::NORMALIZED_MIN_SUM;
        } else if (arg.rfind("--alpha=", 0) == 0) {
            opts.alpha = std::stod(arg.substr(std::string("--alpha=").size()));
        } else if (arg == "--quiet-iter-log") {
            opts.log_decode_iterations = false;
        }
    }
    return opts;
}

PointStats runPoint(const BinaryMatrix& H,
                    const TannerGraph& G,
                    const BeliefPropagation::Params& params,
                    int n,
                    int trials,
                    double p_error,
                    int seed_base) {
    long long frame_errors = 0;
    long long bit_errors = 0;
    long long it_sum = 0;
    long long syndrome_sat = 0;
    long long max_iter_hits = 0;

    const int p_key = static_cast<int>(std::llround(p_error * 1000000.0));
    const std::vector<int> syndrome(H.rows(), 0);

    #pragma omp parallel for reduction(+:frame_errors,bit_errors,it_sum,syndrome_sat,max_iter_hits) schedule(static)
    for (int t = 0; t < trials; ++t) {
        std::mt19937 rng(seed_base + n * 10000 + p_key + t);
        std::bernoulli_distribution flip(std::clamp(p_error, 0.0, 1.0));

        std::vector<int> received(n, 0);
        std::vector<int> erasures(n, 0);
        for (int i = 0; i < n; ++i)
            received[i] = flip(rng) ? 1 : 0;

        BeliefPropagation decoder(G, params);
        const auto x_hat = decoder.decode(syndrome, received, erasures, p_error);

        int frame_bit_errors = 0;
        for (int bit : x_hat)
            frame_bit_errors += (bit & 1);
        bit_errors += frame_bit_errors;
        if (frame_bit_errors > 0)
            frame_errors++;

        it_sum += decoder.lastIterations();
        if (decoder.lastHitMaxIters())
            max_iter_hits++;

        const auto s_check = H.multiply(x_hat);
        bool codeword_ok = true;
        for (int v : s_check) {
            if ((v & 1) != 0) {
                codeword_ok = false;
                break;
            }
        }
        if (codeword_ok)
            syndrome_sat++;
    }

    PointStats out;
    out.ber = static_cast<double>(bit_errors) / static_cast<double>(trials * n);
    out.fer = static_cast<double>(frame_errors) / static_cast<double>(trials);
    out.avg_iter = static_cast<double>(it_sum) / static_cast<double>(trials);
    out.parity_sat_rate = static_cast<double>(syndrome_sat) / static_cast<double>(trials);
    out.max_iter_hit_rate = static_cast<double>(max_iter_hits) / static_cast<double>(trials);
    return out;
}

void runDebugDecodeLog(const BinaryMatrix& H,
                       const TannerGraph& G,
                       const BeliefPropagation::Params& params,
                       int n,
                       double p_error,
                       int seed,
                       const std::string& label) {
    BeliefPropagation::Params debug_params = params;
    debug_params.log_iteration_stats = true;
    debug_params.log_llr_breakdown = false;
    debug_params.log_edge_debug = true;
    debug_params.edge_debug_var = 0;
    BeliefPropagation decoder(G, debug_params);

    std::mt19937 rng(seed);
    std::bernoulli_distribution flip(p_error);

    std::vector<int> received(n, 0);
    std::vector<int> erasures(n, 0);
    for (int i = 0; i < n; ++i)
        received[i] = flip(rng) ? 1 : 0;

    std::cout << "[decode-log] " << label
              << " p=" << std::setprecision(3) << p_error
              << "\n";
    const std::vector<int> no_syndrome;
    (void)decoder.decode(no_syndrome, received, erasures, p_error);
    std::cout << "  hit_max_iters=" << (decoder.lastHitMaxIters() ? "yes" : "no")
              << "\n";
}

void runSweep(const SweepConfig& cfg, const RuntimeOptions& opts) {
    std::cout << "\n=== Sweep " << cfg.label
              << " (n=" << cfg.n
              << ", m=" << cfg.m
              << ", col_w=" << cfg.col_weight
              << ", trials=" << cfg.trials
              << ") ===\n";

    BinaryMatrix H = LDPCGenerator::generatePEG(cfg.m, cfg.n, cfg.col_weight, 42);
    TannerGraph G(H);

    GraphDiagnostics::printDegreeDistribution(
        GraphDiagnostics::variableDegreeDistribution(G), "Variable");
    GraphDiagnostics::printDegreeDistribution(
        GraphDiagnostics::checkDegreeDistribution(G), "Check");

    const int girth_bounded = GraphDiagnostics::estimateGirthBounded(G, 12);
    if (girth_bounded > 0) {
        std::cout << "Estimated girth (bounded search): " << girth_bounded
                  << " (<=12)\n";
    } else {
        std::cout << "Estimated girth (bounded search): >12\n";
    }

    BeliefPropagation::Params params;
    params.max_iters = 80;
    params.damping = 0.0;
    params.mode = opts.mode;
    params.alpha = opts.alpha;
    params.llr_max = 50.0;
    params.convergence_tol = 1e-6;
    params.log_iteration_stats = false;

    CSVWriter csv(cfg.csv_file, "p,ber,fer,avg_iterations,parity_sat_rate,max_iter_hit_rate");

    const char* mode_name = (opts.mode == BeliefPropagation::Mode::SUM_PRODUCT)
        ? "SUM_PRODUCT"
        : "NORMALIZED_MIN_SUM";
    std::cout << "Decoder mode=" << mode_name
              << " alpha=" << opts.alpha
              << " llr_max=" << params.llr_max
              << " max_iters=" << params.max_iters
              << "\n";

    // Sanity checks
    const int sanity_trials = std::min(100, cfg.trials);
    const auto zero_noise = runPoint(H, G, params, cfg.n, sanity_trials, 0.0, 9100000);
    const auto tiny_noise = runPoint(H, G, params, cfg.n, sanity_trials, 0.001, 9200000);

    std::cout << "[sanity] p=0.000  BER=" << zero_noise.ber
              << " FER=" << zero_noise.fer
              << " avg_iter=" << zero_noise.avg_iter
              << " parity_sat=" << zero_noise.parity_sat_rate
              << "\n";
    if (zero_noise.ber > 1e-12 || zero_noise.fer > 1e-12) {
        std::cout << "WARNING: zero-noise sanity failed (expected BER=FER=0)\n";
    }

    std::cout << "[sanity] p=0.001  BER=" << tiny_noise.ber
              << " FER=" << tiny_noise.fer
              << " avg_iter=" << tiny_noise.avg_iter
              << " parity_sat=" << tiny_noise.parity_sat_rate
              << "\n";
    if (tiny_noise.fer > 0.05) {
        std::cout << "WARNING: small-noise sanity FER is unexpectedly high\n";
    }

    std::cout << std::fixed;
    std::vector<double> p_vals;
    std::vector<double> fer_vals;
    bool fer_monotonic = true;

    for (double p_error = cfg.p_start; p_error <= cfg.p_end + 1e-12; p_error += cfg.p_step) {
        std::cout << "log((1-p)/p)="
                  << std::log((1.0 - p_error) / p_error)
                  << "\n";

        if (opts.log_decode_iterations) {
            const int log_seed = 700000 + static_cast<int>(p_error * 1000.0) + cfg.n;
            runDebugDecodeLog(H, G, params, cfg.n, p_error, log_seed, cfg.label);
        }

        const auto stats = runPoint(H, G, params, cfg.n, cfg.trials, p_error, 1234567);
        csv.writeCurve(p_error, stats.ber, stats.fer, stats.avg_iter, stats.parity_sat_rate, stats.max_iter_hit_rate);

        std::cout << "n=" << cfg.n
                  << " p=" << std::setprecision(3) << p_error
                  << " BER=" << std::setprecision(6) << stats.ber
                  << " FER=" << std::setprecision(6) << stats.fer
                  << " avg_iter=" << std::setprecision(2) << stats.avg_iter
                  << " parity_sat=" << std::setprecision(4) << stats.parity_sat_rate
                  << " max_iter_hit=" << std::setprecision(4) << stats.max_iter_hit_rate
                  << "\n";

        if (!fer_vals.empty() && stats.fer + 1e-12 < fer_vals.back()) {
            fer_monotonic = false;
            std::cout << "WARNING: FER non-monotonic between p=" << p_vals.back()
                      << " (FER=" << fer_vals.back() << ") and p=" << p_error
                      << " (FER=" << stats.fer << ")\n";
        }

        p_vals.push_back(p_error);
        fer_vals.push_back(stats.fer);
    }

    std::cout << "FER monotonicity check: " << (fer_monotonic ? "PASS" : "FAIL") << "\n";
}

} // namespace

int main(int argc, char** argv) {
    std::cout << "LiDMaS+ v0.2 Sparse BP (LDPC BSC Sweep)\n";
    std::cout << "Usage flags: --bp=nms | --bp=sum-product | --alpha=0.8 | --quiet-iter-log\n";

    const RuntimeOptions opts = parseOptions(argc, argv);

    const SweepConfig cfg_large{
        .m = 500,
        .n = 1000,
        .col_weight = 3,
        .trials = 200,
        .p_start = 0.01,
        .p_end = 0.10,
        .p_step = 0.01,
        .label = "R1/2-large-SP",
        .csv_file = "ldpc_curve_n1000.csv"
    };

    runSweep(cfg_large, opts);
    return 0;
}
