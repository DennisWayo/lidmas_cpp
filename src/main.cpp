// ================================
// FILE: src/main.cpp
// LDPC + BSC + BP sweeps with diagnostics
// ================================

#include <iomanip>
#include <iostream>
#include <memory>
#include <random>
#include <sstream>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>

#include "codes/LDPCGenerator.h"
#include "core/PluginRegistry.h"
#include "core/RegisterPlugins.h"
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
#include "sim/SurfaceThresholdRunner.h"
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

std::string joinNames(const std::vector<std::string>& names) {
    std::string out;
    for (size_t i = 0; i < names.size(); ++i) {
        if (i > 0) out += "|";
        out += names[i];
    }
    return out;
}

void printHelp(const PluginRegistry& plugins) {
    const std::string surface_decoders = joinNames(plugins.list());
    std::cout << "LiDMaS+ usage\n"
              << "  ./lidmas                      Run classical LDPC BSC sweep (default)\n"
              << "  ./lidmas --qec=css_demo       Run CSS demo using BP decoder core\n"
              << "  ./lidmas --surface_demo=stub  Run surface pipeline demo (stub)\n"
              << "  ./lidmas --surface_demo=mwpm  Run surface pipeline demo (MWPM)\n"
              << "  ./lidmas --surface_demo=uf    Run surface pipeline demo (UF placeholder)\n"
              << "  ./lidmas --surface_demo=neural_mwpm  Run surface pipeline demo (neural-guided MWPM)\n"
              << "  ./lidmas --surface_threshold [--decoder=" << surface_decoders << "] [--d=3,5,7]\n"
              << "                               [--p_start=0.01 --p_end=0.15 --p_step=0.01]\n"
              << "                               [--trials=2000 --seed=12345 --out=surface_threshold.csv]\n"
              << "                               [--threads=<N>]\n"
              << "                               [--min_trials=200 --max_trials=20000 --batch_trials=200]\n"
              << "                               [--target_ci_halfwidth=0.01 --target_rel_ci=0.10]\n"
              << "                               [--auto_threshold]\n"
              << "                               [--estimate_threshold]\n"
              << "                               [--scaling_fit]\n"
              << "                               [--monotonic_smooth]\n"
              << "  ./lidmas --smoke              Run lightweight surface smoke checks\n"
              << "\n"
              << "Flags\n"
              << "  --bp=sum-product              Use sum-product BP\n"
              << "  --bp=nms                      Use normalized min-sum BP\n"
              << "  --alpha=<value>               Set normalized min-sum alpha\n"
              << "  --neural_model=<path>         Neural model JSON file for neural_mwpm\n"
              << "  --weight_mode=<uniform|neural|llr> Select shared surface weight mode (default uniform)\n"
              << "  --uf_weighted                 Enable weighted Union-Find growth\n"
              << "  --neural_weights=<path>       Neural weights JSON for weighted uf\n"
              << "  --llr_p_data=<x>              LLR mode data-edge probability (default sweep p)\n"
              << "  --llr_p_meas=<x>              LLR mode measurement-edge probability (default sweep p)\n"
              << "  --llr_p_idle=<x>              LLR mode idle-edge probability (default sweep p)\n"
              << "  --llr_clamp_min=<x>           LLR probability clamp min (default 1e-12)\n"
              << "  --llr_clamp_max=<x>           LLR probability clamp max (default 1-1e-12)\n"
              << "  --mwpm_weight_scale=<x>       MWPM weight scaling factor (default 1000)\n"
              << "  --min_trials=<N>              Adaptive threshold minimum trials per point\n"
              << "  --max_trials=<N>              Adaptive threshold maximum trials per point\n"
              << "  --batch_trials=<N>            Adaptive threshold trials per increment\n"
              << "  --target_ci_halfwidth=<x>     Stop when absolute LER CI half-width <= x\n"
              << "  --target_rel_ci=<x>           Stop when relative LER CI half-width <= x\n"
              << "  --threads=<N>                 OpenMP threads for surface_threshold\n"
              << "  --auto_threshold              Estimate threshold crossings after sweep\n"
              << "  --estimate_threshold          Pairwise crossing estimate of p_c\n"
              << "  --scaling_fit                Finite-size scaling fit for p_c and nu\n"
              << "  --quiet-iter-log              Disable per-iteration decode logging\n"
              << "  surface decoders              " << surface_decoders << "\n"
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

std::vector<int> parseDistancesCsv(const std::string& s) {
    std::vector<int> out;
    if (s.empty()) return out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) {
        if (item.empty()) continue;
        const int d = std::stoi(item);
        if (d >= 3 && (d % 2) == 1) out.push_back(d);
    }
    return out;
}

void runQecSurfaceDemo(const std::string& mode,
                       const std::string& weight_mode,
                       bool uf_weighted,
                       const std::string& neural_weights_path,
                       const std::string& neural_model_path,
                       double llr_p_data,
                       double llr_p_meas,
                       double llr_p_idle,
                       double llr_clamp_min,
                       double llr_clamp_max,
                       double mwpm_weight_scale,
                       const PluginRegistry& plugins) {
    std::string decoder = mode;
    if (decoder.empty()) decoder = "stub";
    if (decoder == "mwpm_stub") decoder = "stub";
    const std::vector<std::string> available = plugins.list();
    if (std::find(available.begin(), available.end(), decoder) == available.end()) {
        std::cout << "Unknown surface demo mode '" << mode
                  << "', falling back to stub.\n";
        decoder = "stub";
    }
    std::cout << (decoder == "mwpm"
                     ? "LiDMaS+ Surface MWPM Demo (experimental)\n"
                     : (decoder == "uf"
                            ? "LiDMaS+ Surface UF Demo (experimental)\n"
                            : (decoder == "neural_mwpm"
                                   ? "LiDMaS+ Surface Neural MWPM Demo (experimental)\n"
                                   : "LiDMaS+ Surface Stub Demo (experimental)\n")));

    SurfaceSweepConfig cfg;
    cfg.d = 3;
    cfg.trials = 200;
    cfg.seed_base = 8400000;
    cfg.p_values = {0.00, 0.02, 0.05, 0.08};
    cfg.decoder_name = decoder;
    cfg.weight_mode = weight_mode;
    cfg.uf_weighted = uf_weighted || (weight_mode == "neural") || (weight_mode == "llr");
    cfg.llr_p_data = llr_p_data;
    cfg.llr_p_meas = llr_p_meas;
    cfg.llr_p_idle = llr_p_idle;
    cfg.llr_clamp_min = llr_clamp_min;
    cfg.llr_clamp_max = llr_clamp_max;
    cfg.mwpm_weight_scale = mwpm_weight_scale;
    cfg.neural_weights_path = neural_weights_path;
    cfg.neural_model_path = neural_model_path;

    const auto points = SurfaceSimulation::run_decoder_sweep(cfg, plugins);
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
    PluginRegistry plugins;
    RegisterAllPlugins(plugins);
    std::string weight_mode = getValuePrefix(args, "--weight_mode=");
    if (weight_mode.empty()) weight_mode = "uniform";
    if (weight_mode != "uniform" && weight_mode != "neural" && weight_mode != "llr") {
        std::cout << "Unknown --weight_mode='" << weight_mode
                  << "', falling back to uniform.\n";
        weight_mode = "uniform";
    }
    const std::string llr_p_data_arg = getValuePrefix(args, "--llr_p_data=");
    const std::string llr_p_meas_arg = getValuePrefix(args, "--llr_p_meas=");
    const std::string llr_p_idle_arg = getValuePrefix(args, "--llr_p_idle=");
    const std::string llr_clamp_min_arg = getValuePrefix(args, "--llr_clamp_min=");
    const std::string llr_clamp_max_arg = getValuePrefix(args, "--llr_clamp_max=");
    const std::string mwpm_weight_scale_arg = getValuePrefix(args, "--mwpm_weight_scale=");
    const double llr_p_data = llr_p_data_arg.empty() ? -1.0 : std::stod(llr_p_data_arg);
    const double llr_p_meas = llr_p_meas_arg.empty() ? -1.0 : std::stod(llr_p_meas_arg);
    const double llr_p_idle = llr_p_idle_arg.empty() ? -1.0 : std::stod(llr_p_idle_arg);
    const double llr_clamp_min = llr_clamp_min_arg.empty() ? 1e-12 : std::stod(llr_clamp_min_arg);
    const double llr_clamp_max = llr_clamp_max_arg.empty() ? (1.0 - 1e-12) : std::stod(llr_clamp_max_arg);
    const double mwpm_weight_scale = mwpm_weight_scale_arg.empty() ? 1000.0 : std::stod(mwpm_weight_scale_arg);
    const bool uf_weighted = hasFlag(args, "--uf_weighted");
    const std::string neural_weights_path = getValuePrefix(args, "--neural_weights=");
    const std::string neural_model_path = getValuePrefix(args, "--neural_model=");
    if (hasFlag(args, "--help") || hasFlag(args, "-h")) {
        printHelp(plugins);
        return 0;
    }
    if (hasFlag(args, "--smoke")) {
        const bool ok = run_smoke_tests();
        return ok ? 0 : 1;
    }
    if (hasFlag(args, "--surface_threshold")) {
        SurfaceThresholdConfig cfg;
        bool adaptive_requested = false;
        const std::string decoder = getValuePrefix(args, "--decoder=");
        if (!decoder.empty()) cfg.decoder_name = decoder;
        const std::string d_csv = getValuePrefix(args, "--d=");
        if (!d_csv.empty()) {
            const auto dlist = parseDistancesCsv(d_csv);
            if (!dlist.empty()) cfg.distances = dlist;
        }
        const std::string p_start = getValuePrefix(args, "--p_start=");
        if (!p_start.empty()) cfg.p_start = std::stod(p_start);
        const std::string p_end = getValuePrefix(args, "--p_end=");
        if (!p_end.empty()) cfg.p_end = std::stod(p_end);
        const std::string p_step = getValuePrefix(args, "--p_step=");
        if (!p_step.empty()) cfg.p_step = std::stod(p_step);
        const std::string trials = getValuePrefix(args, "--trials=");
        if (!trials.empty()) {
            cfg.trials = std::stoi(trials);
            cfg.trials_explicit = true;
        }
        const std::string seed = getValuePrefix(args, "--seed=");
        if (!seed.empty()) cfg.seed = static_cast<uint64_t>(std::stoull(seed));
        const std::string out = getValuePrefix(args, "--out=");
        if (!out.empty()) cfg.out_csv = out;
        if (hasFlag(args, "--monotonic_smooth")) cfg.monotonic_smooth = true;
        cfg.weight_mode = weight_mode;
        if (uf_weighted || weight_mode == "neural" || weight_mode == "llr") cfg.uf_weighted = true;
        cfg.llr_p_data = llr_p_data;
        cfg.llr_p_meas = llr_p_meas;
        cfg.llr_p_idle = llr_p_idle;
        cfg.llr_clamp_min = llr_clamp_min;
        cfg.llr_clamp_max = llr_clamp_max;
        cfg.mwpm_weight_scale = mwpm_weight_scale;
        const std::string min_trials = getValuePrefix(args, "--min_trials=");
        if (!min_trials.empty()) {
            cfg.min_trials = std::stoi(min_trials);
            adaptive_requested = true;
        }
        const std::string max_trials = getValuePrefix(args, "--max_trials=");
        if (!max_trials.empty()) {
            cfg.max_trials = std::stoi(max_trials);
            adaptive_requested = true;
        }
        const std::string batch_trials = getValuePrefix(args, "--batch_trials=");
        if (!batch_trials.empty()) {
            cfg.batch_trials = std::stoi(batch_trials);
            adaptive_requested = true;
        }
        const std::string target_abs = getValuePrefix(args, "--target_ci_halfwidth=");
        if (!target_abs.empty()) {
            cfg.target_ci_halfwidth = std::stod(target_abs);
            adaptive_requested = true;
        }
        const std::string target_rel = getValuePrefix(args, "--target_rel_ci=");
        if (!target_rel.empty()) {
            cfg.target_rel_ci = std::stod(target_rel);
            adaptive_requested = true;
        }
        const std::string threads = getValuePrefix(args, "--threads=");
        if (!threads.empty()) {
            cfg.threads = std::max(1, std::stoi(threads));
        }
        if (hasFlag(args, "--auto_threshold")) {
            cfg.auto_threshold = true;
            cfg.estimate_threshold = true; // backward-compatible alias
        }
        if (hasFlag(args, "--estimate_threshold")) cfg.estimate_threshold = true;
        if (hasFlag(args, "--scaling_fit")) cfg.scaling_fit = true;
        cfg.adaptive_enabled = adaptive_requested;
        cfg.neural_weights_path = neural_weights_path;
        cfg.neural_model_path = neural_model_path;
        return SurfaceThresholdRunner::run(cfg, plugins);
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
        runQecSurfaceDemo(mode, weight_mode, uf_weighted, neural_weights_path, neural_model_path,
                          llr_p_data, llr_p_meas, llr_p_idle, llr_clamp_min, llr_clamp_max, mwpm_weight_scale,
                          plugins);
        return 0;
    }

    const std::string qec_mode = getValuePrefix(args, "--qec=");
    if (qec_mode == "css_demo") {
        runQecCssDemo(opts);
        return 0;
    }
    if (qec_mode == "surface_stub") {
        runQecSurfaceDemo("stub", weight_mode, uf_weighted, neural_weights_path, neural_model_path,
                          llr_p_data, llr_p_meas, llr_p_idle, llr_clamp_min, llr_clamp_max, mwpm_weight_scale,
                          plugins);
        return 0;
    }
    if (qec_mode == "surface_mwpm") {
        runQecSurfaceDemo("mwpm", weight_mode, uf_weighted, neural_weights_path, neural_model_path,
                          llr_p_data, llr_p_meas, llr_p_idle, llr_clamp_min, llr_clamp_max, mwpm_weight_scale,
                          plugins);
        return 0;
    }
    if (qec_mode == "surface_uf") {
        runQecSurfaceDemo("uf", weight_mode, uf_weighted, neural_weights_path, neural_model_path,
                          llr_p_data, llr_p_meas, llr_p_idle, llr_clamp_min, llr_clamp_max, mwpm_weight_scale,
                          plugins);
        return 0;
    }
    if (qec_mode == "surface_neural_mwpm") {
        runQecSurfaceDemo("neural_mwpm", weight_mode, uf_weighted, neural_weights_path, neural_model_path,
                          llr_p_data, llr_p_meas, llr_p_idle, llr_clamp_min, llr_clamp_max, mwpm_weight_scale,
                          plugins);
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
