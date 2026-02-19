// ================================
// FILE: src/main.cpp
// LDPC + BSC + BP sweeps with diagnostics
// ================================

#include <iomanip>
#include <iostream>
#include <memory>
#include <random>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>

#include "codes/LDPCGenerator.h"
#include "decoders/BPDecoderAdapter.h"
#include "decoders/BeliefPropagation.h"
#include "graph/GraphDiagnostics.h"
#include "qec/PauliChannelAdapter.h"
#include "qec/QuantumCSSSimulator.h"
#include "graph/TannerGraph.h"
#include "sim/CSSSimulation.h"
#include "sim/LDPCSimulation.h"
#include "sim/SmokeTests.h"
#include "sim/SurfaceSimulation.h"
#include "utils/BSCChannel.h"
#include "utils/CSVWriter.h"
#include "utils/SeedUtils.h"
#include "utils/SyndromeUtils.h"

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
    std::string qec_mode;
    bool selftest = false;
};

struct PointStats {
    double ber = 0.0;
    double fer = 0.0;
    double avg_iter = 0.0;
    double parity_sat_rate = 0.0;
    double max_iter_hit_rate = 0.0;
};

std::vector<std::string> toArgs(int argc, char** argv) {
    std::vector<std::string> args;
    args.reserve(std::max(0, argc - 1));
    for (int i = 1; i < argc; ++i) {
        args.emplace_back(argv[i]);
    }
    return args;
}

bool hasFlag(const std::vector<std::string>& args, const std::string& flag) {
    return std::find(args.begin(), args.end(), flag) != args.end();
}

std::string getValuePrefix(const std::vector<std::string>& args, const std::string& prefix) {
    for (const auto& arg : args) {
        if (arg.rfind(prefix, 0) == 0) {
            return arg.substr(prefix.size());
        }
    }
    return "";
}

void printHelp() {
    std::cout << "LiDMaS+ usage\n"
              << "  ./lidmas                      Run classical LDPC BSC sweep (default)\n"
              << "  ./lidmas --qec=css_demo       Run CSS demo using BP decoder core\n"
              << "  ./lidmas --surface_demo=stub  Run surface pipeline demo (stub)\n"
              << "  ./lidmas --surface_demo=mwpm  Run surface pipeline demo (MWPM)\n"
              << "\n"
              << "Flags\n"
              << "  --bp=sum-product              Use sum-product BP\n"
              << "  --bp=nms                      Use normalized min-sum BP\n"
              << "  --alpha=<value>               Set normalized min-sum alpha\n"
              << "  --quiet-iter-log              Disable per-iteration decode logging\n"
              << "  --help, -h                    Show this help text\n";
}

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
        } else if (arg.rfind("--qec=", 0) == 0) {
            opts.qec_mode = arg.substr(std::string("--qec=").size());
        } else if (arg == "--selftest") {
            opts.selftest = true;
        }
    }
    return opts;
}

BeliefPropagation::Params makeParams(const RuntimeOptions& opts) {
    BeliefPropagation::Params params;
    params.max_iters = 80;
    params.damping = 0.0;
    params.mode = opts.mode;
    params.alpha = opts.alpha;
    params.llr_max = 50.0;
    params.convergence_tol = 1e-6;
    params.log_iteration_stats = false;
    return params;
}

void runQecCssDemo(const RuntimeOptions& opts) {
    std::cout << "LiDMaS+ v0.6 Quantum CSS Demo\n";

    // Minimal commuting toy CSS pair for pipeline validation.
    BinaryMatrix Hx(2, 5);
    Hx.set(0, 0, 1); Hx.set(0, 1, 1);
    Hx.set(1, 1, 1); Hx.set(1, 2, 1);

    BinaryMatrix Hz(2, 5);
    Hz.set(0, 0, 1); Hz.set(0, 1, 1); Hz.set(0, 2, 1);
    Hz.set(1, 3, 1); Hz.set(1, 4, 1);

    LogicalPair logicals;
    logicals.LX = {1, 0, 0, 1, 0};
    logicals.LZ = {0, 0, 1, 0, 1};

    const BeliefPropagation::Params params = makeParams(opts);

    TannerGraph Gx(Hx);
    TannerGraph Gz(Hz);
    const auto dec_x_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(Gz, params);
    };
    const auto dec_z_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(Gx, params);
    };

    PauliChannelAdapter qec_channel;
    QuantumCSSSimulator sim(Hx, Hz, dec_x_factory, dec_z_factory, qec_channel);

    CSVWriter csv("qec_css_demo.csv", "p,ler_total,ler_x,ler_z,avg_iter_x,avg_iter_z");
    const int trials = 200;

    {
        const auto s = CSSSimulation::run_point(sim, 0.0, trials, 7200000, &logicals);
        std::cout << "[sanity] p=0.000"
                  << "  LER_total=" << s.ler_total
                  << "  LER_X=" << s.ler_x
                  << "  LER_Z=" << s.ler_z
                  << "  avg_iter_X=" << s.avg_iter_x
                  << "  avg_iter_Z=" << s.avg_iter_z
                  << "\n";
    }

    const std::vector<double> p_values{0.001, 0.010, 0.020};
    const auto points = CSSSimulation::run_css_demo(sim, p_values, trials, 7300000, &logicals);
    for (const auto& stats : points) {
        csv.writeCurve(
            stats.p,
            stats.ler_total,
            stats.ler_x,
            stats.ler_z,
            stats.avg_iter_x,
            stats.avg_iter_z
        );

        std::cout << "p=" << std::fixed << std::setprecision(3) << stats.p
                  << "  LER_total=" << std::setprecision(6) << stats.ler_total
                  << "  LER_X=" << std::setprecision(6) << stats.ler_x
                  << "  LER_Z=" << std::setprecision(6) << stats.ler_z
                  << "  avg_iter_X=" << std::setprecision(2) << stats.avg_iter_x
                  << "  avg_iter_Z=" << std::setprecision(2) << stats.avg_iter_z
                  << "\n";
    }
}

void runQecSurfaceDemo(const std::string& mode) {
    const bool use_mwpm = (mode == "mwpm");
    if (!use_mwpm && mode != "stub") {
        std::cout << "Unknown surface demo mode '" << mode
                  << "', falling back to stub.\n";
    }
    std::cout << (use_mwpm ? "LiDMaS+ Surface MWPM Demo (experimental)\n"
                           : "LiDMaS+ Surface Stub Demo (experimental)\n");

    SurfaceStubSweepConfig cfg;
    cfg.d = 3;
    cfg.trials = 200;
    cfg.seed_base = 8400000;
    cfg.p_values = {0.00, 0.02, 0.05, 0.08};

    const auto points = use_mwpm
        ? SurfaceSimulation::run_mwpm_sweep(cfg)
        : SurfaceSimulation::run_stub_sweep(cfg);
    for (const auto& s : points) {
        std::cout << "p=" << std::fixed << std::setprecision(3) << s.p
                  << "  defect_count_avg=" << std::setprecision(4) << s.defect_count_avg
                  << "  correction_weight_avg=" << std::setprecision(4) << s.correction_weight_avg
                  << "  logical_fail_rate=" << std::setprecision(6) << s.logical_fail_rate
                  << "\n";
    }
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
    BPDecoderAdapter decoder(G, debug_params);

    std::mt19937 rng(seed);
    std::bernoulli_distribution flip(p_error);

    std::vector<int> received(n, 0);
    std::vector<int> erasures(n, 0);
    for (int i = 0; i < n; ++i)
        received[i] = flip(rng) ? 1 : 0;

    std::cout << "[decode-log] " << label
              << " p=" << std::setprecision(3) << p_error
              << "\n";
    const std::vector<int> no_syndrome = zero_syndrome(H.rows());
    DecodeRequest req;
    req.syndrome = &no_syndrome;
    req.received_bits = &received;
    req.erasures = &erasures;
    req.p_error = p_error;
    const DecodeResult dec = decoder.decode(req);
    std::cout << "  hit_max_iters=" << (dec.hit_max_iters ? "yes" : "no")
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

    const BeliefPropagation::Params params = makeParams(opts);
    BSCChannel channel;
    const auto decoder_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(G, params);
    };

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
    const auto zero_noise = LDPCSimulation::run_point(H, decoder_factory, channel, cfg.n, sanity_trials, 0.0, 9100000);
    const auto tiny_noise = LDPCSimulation::run_point(H, decoder_factory, channel, cfg.n, sanity_trials, 0.001, 9200000);

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
            const int log_seed = ldpc_debug_seed(p_error, cfg.n);
            runDebugDecodeLog(H, G, params, cfg.n, p_error, log_seed, cfg.label);
        }

        const auto stats = LDPCSimulation::run_point(
            H, decoder_factory, channel, cfg.n, cfg.trials, p_error, 1234567);
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
    const std::vector<std::string> args = toArgs(argc, argv);
    if (hasFlag(args, "--help") || hasFlag(args, "-h")) {
        printHelp();
        return 0;
    }

    const RuntimeOptions opts = parseOptions(argc, argv);
    if (opts.selftest) {
        const bool ok = run_self_tests(makeParams(opts));
        return ok ? 0 : 1;
    }
    const bool has_surface_demo_flag = hasFlag(args, "--surface_demo");
    const std::string surface_demo_mode = getValuePrefix(args, "--surface_demo=");
    if (has_surface_demo_flag || !surface_demo_mode.empty()) {
        const std::string mode = surface_demo_mode.empty() ? "stub" : surface_demo_mode;
        runQecSurfaceDemo(mode);
        return 0;
    }

    const std::string qec_mode = getValuePrefix(args, "--qec=");
    if (qec_mode == "css_demo") {
        runQecCssDemo(opts);
        return 0;
    }
    if (qec_mode == "surface_stub") {
        runQecSurfaceDemo("stub");
        return 0;
    }
    if (qec_mode == "surface_mwpm") {
        runQecSurfaceDemo("mwpm");
        return 0;
    }

    std::cout << "LiDMaS+ v0.6\n";
    std::cout << "Usage flags: --bp=nms | --bp=sum-product | --alpha=0.8 | --quiet-iter-log\n";

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
