#include "sim/SmokeTests.h"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>

#include "codes/LDPCGenerator.h"
#include "cv/gaussian_noise.hpp"
#include "decoders/BPDecoderAdapter.h"
#include "gkp/gkp_digitizer.hpp"
#include "graph/TannerGraph.h"
#include "hybrid/hybrid_engine.hpp"
#include "qec/PauliChannelAdapter.h"
#include "qec/QuantumCSSSimulator.h"
#include "sim/CSSSimulation.h"
#include "sim/LDPCSimulation.h"
#include "sim/SurfaceSimulation.h"
#include "sim/SurfaceThresholdRunner.h"
#include "LLRWeightField.h"
#include "surface/MWPMDecoder.h"
#include "surface/SurfaceCode.h"
#include "utils/BSCChannel.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

bool near_zero(double x, double eps = 1e-12) {
    return std::abs(x) <= eps;
}

bool syndrome_is_zero(const std::vector<int>& s) {
    for (int v : s) {
        if ((v & 1) != 0) return false;
    }
    return true;
}

bool readFile(const std::string& path, std::string& out) {
    std::ifstream in(path);
    if (!in.is_open()) return false;
    out.assign((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    return true;
}

bool extractJsonNumber(const std::string& json, const std::string& key, double& value_out) {
    const std::string token = "\"" + key + "\"";
    const size_t pos = json.find(token);
    if (pos == std::string::npos) return false;
    const size_t colon = json.find(':', pos + token.size());
    if (colon == std::string::npos) return false;
    size_t start = json.find_first_not_of(" \t\r\n", colon + 1);
    if (start == std::string::npos) return false;
    if (json.compare(start, 4, "null") == 0) return false;
    size_t end = start;
    while (end < json.size()) {
        const char ch = json[end];
        if ((ch >= '0' && ch <= '9') || ch == '+' || ch == '-' || ch == '.' || ch == 'e' || ch == 'E') {
            ++end;
            continue;
        }
        break;
    }
    if (end <= start) return false;
    try {
        value_out = std::stod(json.substr(start, end - start));
        return std::isfinite(value_out);
    } catch (...) {
        return false;
    }
}

} // namespace

bool run_self_tests(const BeliefPropagation::Params& params) {
    std::cout << "[selftest] running...\n";

    // LDPC sanity on a small deterministic PEG code.
    const int m = 100;
    const int n = 200;
    const BinaryMatrix H = LDPCGenerator::generatePEG(m, n, 3, 42);
    const TannerGraph G(H);
    BSCChannel channel;

    const auto decoder_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(G, params);
    };

    const auto s0 = LDPCSimulation::run_point(H, decoder_factory, channel, n, 20, 0.0, 9100000);
    const auto s1 = LDPCSimulation::run_point(H, decoder_factory, channel, n, 20, 0.001, 9200000);

    if (!near_zero(s0.ber) || !near_zero(s0.fer) || !near_zero(1.0 - s0.parity_sat_rate)) {
        std::cerr << "[selftest] LDPC p=0 failed\n";
        return false;
    }
    if (!near_zero(1.0 - s1.parity_sat_rate)) {
        std::cerr << "[selftest] LDPC parity sanity at p=0.001 failed\n";
        return false;
    }

    // CSS sanity at zero noise.
    BinaryMatrix Hx(2, 5);
    Hx.set(0, 0, 1); Hx.set(0, 1, 1);
    Hx.set(1, 1, 1); Hx.set(1, 2, 1);

    BinaryMatrix Hz(2, 5);
    Hz.set(0, 0, 1); Hz.set(0, 1, 1); Hz.set(0, 2, 1);
    Hz.set(1, 3, 1); Hz.set(1, 4, 1);

    const TannerGraph Gx(Hx);
    const TannerGraph Gz(Hz);
    const auto dec_x_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(Gz, params);
    };
    const auto dec_z_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(Gx, params);
    };

    PauliChannelAdapter qec_channel;
    QuantumCSSSimulator sim(Hx, Hz, dec_x_factory, dec_z_factory, qec_channel);

    LogicalPair logicals;
    logicals.LX = {1, 0, 0, 1, 0};
    logicals.LZ = {0, 0, 1, 0, 1};

    const auto css0 = CSSSimulation::run_point(sim, 0.0, 20, 7200000, &logicals);
    if (!near_zero(css0.ler_total)) {
        std::cerr << "[selftest] CSS p=0 failed\n";
        return false;
    }

    // LLR weight formalism sanity checks.
    {
        const LLRWeightField w01(0.01, 0.01, 0.01);
        const LLRWeightField w10(0.10, 0.10, 0.10);
        const LLRWeightField w30(0.30, 0.30, 0.30);
        const double a = w01.edge_weight(0, 1);
        const double b = w10.edge_weight(0, 1);
        const double c = w30.edge_weight(0, 1);
        if (!(a > b && b > c)) {
            std::cerr << "[selftest] LLR monotonicity failed: expected w(0.01)>w(0.1)>w(0.3)\n";
            return false;
        }

        const LLRWeightField wClamp(0.0, 0.0, 0.0, 1e-12, 1.0 - 1e-12);
        const double wc = wClamp.edge_weight(0, 1);
        if (!std::isfinite(wc)) {
            std::cerr << "[selftest] LLR clamp failed: p=0 produced non-finite weight\n";
            return false;
        }

#ifdef _OPENMP
        auto computeValues = [](int threads) {
            std::vector<double> values(4096, 0.0);
#pragma omp parallel for schedule(static) num_threads(threads)
            for (int i = 0; i < 4096; ++i) {
                const LLRWeightField wf(0.02, 0.02, 0.02, 1e-12, 1.0 - 1e-12);
                values[static_cast<size_t>(i)] = wf.edge_weight(i, i + 1);
            }
            return values;
        };
        const auto v1 = computeValues(1);
        const auto v8 = computeValues(8);
        if (v1.size() != v8.size()) {
            std::cerr << "[selftest] LLR threaded determinism failed (threads=1 vs 8)\n";
            return false;
        }
        for (size_t i = 0; i < v1.size(); ++i) {
            if (std::abs(v1[i] - v8[i]) > 1e-15) {
                std::cerr << "[selftest] LLR threaded determinism failed at index " << i << "\n";
                return false;
            }
        }
#endif
    }

    // Surface MWPM sanity checks (deterministic, no RNG).
    {
        SurfaceCode scode(3);
        MWPMDecoder mwpm(scode, MWPMDecoder::GraphMode::FULL);

        // Case 1: single-qubit X error should produce syndrome and be corrected.
        SurfaceSyndrome syn1;
        syn1.ex.assign(scode.n(), 0);
        syn1.ex[0] = 1;
        syn1.sz = scode.Hz().multiply(syn1.ex);
        for (int& v : syn1.sz) v &= 1;
        if (syndrome_is_zero(syn1.sz)) {
            std::cerr << "[selftest] Surface MWPM single-error syndrome generation failed\n";
            return false;
        }
        const auto corr1 = mwpm.decode(syn1);
        std::vector<int> res1(scode.n(), 0);
        for (int i = 0; i < scode.n(); ++i) res1[i] = (syn1.ex[i] ^ corr1[i]) & 1;
        auto sz_res1 = scode.Hz().multiply(res1);
        for (int& v : sz_res1) v &= 1;
        if (!syndrome_is_zero(sz_res1)) {
            std::cerr << "[selftest] Surface MWPM single-error correction failed\n";
            return false;
        }

        // Case 2: two nearby errors should be matched and corrected.
        SurfaceSyndrome syn2;
        syn2.ex.assign(scode.n(), 0);
        syn2.ex[0] = 1;
        syn2.ex[1] = 1;
        syn2.sz = scode.Hz().multiply(syn2.ex);
        for (int& v : syn2.sz) v &= 1;
        const auto corr2 = mwpm.decode(syn2);
        std::vector<int> res2(scode.n(), 0);
        for (int i = 0; i < scode.n(); ++i) res2[i] = (syn2.ex[i] ^ corr2[i]) & 1;
        auto sz_res2 = scode.Hz().multiply(res2);
        for (int& v : sz_res2) v &= 1;
        if (!syndrome_is_zero(sz_res2)) {
            std::cerr << "[selftest] Surface MWPM two-error correction failed\n";
            return false;
        }

        // Case 3: zero-noise input should keep zero defects and zero logical fail.
        SurfaceSyndrome syn0;
        syn0.ex.assign(scode.n(), 0);
        syn0.sz.assign(scode.mz(), 0);
        const auto corr0 = mwpm.decode(syn0);
        int weight0 = 0;
        for (int bit : corr0) weight0 += (bit & 1);
        if (weight0 != 0) {
            std::cerr << "[selftest] Surface MWPM zero-noise correction is non-zero\n";
            return false;
        }
    }

    // Deterministic regression for planar boundary matching on d=5.
    {
        SurfaceCode scode(5);
        MWPMDecoder mwpm(scode, MWPMDecoder::GraphMode::FULL);

        SurfaceSyndrome syn;
        syn.sz.assign(scode.mz(), 0);
        syn.sz[2] = 1; // row-major defect at (r=0,c=2) on (d-1)x(d-1)=4x4 Z-check grid.

        std::vector<int> corr;
        try {
            corr = mwpm.decode(syn);
        } catch (const std::exception& ex) {
            std::cerr << "[selftest] Surface MWPM d=5 single-defect decode threw: "
                      << ex.what() << "\n";
            return false;
        }

        auto syn_out = scode.Hz().multiply(corr);
        for (int& v : syn_out) v &= 1;
        if (syn_out.size() != syn.sz.size()) {
            std::cerr << "[selftest] Surface MWPM d=5 single-defect size mismatch\n";
            return false;
        }
        for (size_t i = 0; i < syn_out.size(); ++i) {
            if ((syn_out[i] & 1) != (syn.sz[i] & 1)) {
                std::cerr << "[selftest] Surface MWPM d=5 single-defect syndrome mismatch\n";
                return false;
            }
        }
    }

    // Randomized fixed-seed full-graph syndrome-reproduction checks on d=3 and d=5.
    {
        const std::vector<int> ds{3, 5};
        const std::vector<double> ps{0.01, 0.05};
        for (int d : ds) {
            SurfaceCode scode(d);
            MWPMDecoder mwpm(scode, MWPMDecoder::GraphMode::FULL);
            for (double p : ps) {
                for (int t = 0; t < 12; ++t) {
                    const uint64_t seed = 8100000ULL
                        + static_cast<uint64_t>(d) * 10000ULL
                        + static_cast<uint64_t>(std::llround(p * 1000.0)) * 100ULL
                        + static_cast<uint64_t>(t);
                    const SurfaceSyndrome syn = SurfaceSyndrome::sample(scode, p, p, seed);

                    SurfaceSyndrome syn_z;
                    syn_z.sz = syn.sz;
                    const auto corr_z = mwpm.decode(syn_z);
                    auto got_sz = scode.Hz().multiply(corr_z);
                    for (int& v : got_sz) v &= 1;
                    if (got_sz != syn.sz) {
                        std::cerr << "[selftest] Surface MWPM full-graph Z-syndrome mismatch at d="
                                  << d << " p=" << p << " t=" << t << "\n";
                        return false;
                    }

                    SurfaceSyndrome syn_x;
                    syn_x.sx = syn.sx;
                    const auto corr_x = mwpm.decode(syn_x);
                    auto got_sx = scode.Hx().multiply(corr_x);
                    for (int& v : got_sx) v &= 1;
                    if (got_sx != syn.sx) {
                        std::cerr << "[selftest] Surface MWPM full-graph X-syndrome mismatch at d="
                                  << d << " p=" << p << " t=" << t << "\n";
                        return false;
                    }
                }
            }
        }
    }

    std::cout << "[selftest] PASS\n";
    return true;
}

bool run_smoke_tests() {
    std::cout << "[smoke] running...\n";

    // Deterministic full-graph MWPM syndrome reproduction checks.
    for (int d : {3, 5}) {
        SurfaceCode scode(d);
        MWPMDecoder mwpm(scode, MWPMDecoder::GraphMode::FULL);
        for (double p : {0.01, 0.05}) {
            for (int t = 0; t < 6; ++t) {
                const uint64_t seed = 9100000ULL
                    + static_cast<uint64_t>(d) * 10000ULL
                    + static_cast<uint64_t>(std::llround(p * 1000.0)) * 100ULL
                    + static_cast<uint64_t>(t);
                const SurfaceSyndrome syn = SurfaceSyndrome::sample(scode, p, p, seed);

                SurfaceSyndrome syn_z;
                syn_z.sz = syn.sz;
                const auto corr_z = mwpm.decode(syn_z);
                auto got_sz = scode.Hz().multiply(corr_z);
                for (int& v : got_sz) v &= 1;
                if (got_sz != syn.sz) {
                    std::cerr << "[smoke] full-graph MWPM Z-syndrome mismatch at d="
                              << d << " p=" << p << " t=" << t << "\n";
                    return false;
                }

                SurfaceSyndrome syn_x;
                syn_x.sx = syn.sx;
                const auto corr_x = mwpm.decode(syn_x);
                auto got_sx = scode.Hx().multiply(corr_x);
                for (int& v : got_sx) v &= 1;
                if (got_sx != syn.sx) {
                    std::cerr << "[smoke] full-graph MWPM X-syndrome mismatch at d="
                              << d << " p=" << p << " t=" << t << "\n";
                    return false;
                }
            }
        }
    }

    SurfaceSweepConfig cfg;
    cfg.d = 3;
    cfg.trials = 100;
    cfg.seed_base = 12345;
    cfg.p_values = {0.0};
    cfg.decoder_name = "mwpm";
    cfg.mwpm_graph = "full";

    const auto points = SurfaceSimulation::run_decoder_sweep(cfg);
    if (points.empty()) {
        std::cerr << "[smoke] empty surface result set\n";
        return false;
    }
    if (points.front().logical_fail_rate > 1e-12) {
        std::cerr << "[smoke] expected LER=0 at p=0 for d=3 mwpm, got "
                  << points.front().logical_fail_rate << "\n";
        return false;
    }

    SurfaceSweepConfig mwpm_cfg;
    mwpm_cfg.d = 3;
    mwpm_cfg.trials = 100;
    mwpm_cfg.seed_base = 32345;
    mwpm_cfg.p_values = {0.05};
    mwpm_cfg.decoder_name = "mwpm";
    mwpm_cfg.mwpm_graph = "full";
    const auto mwpm_points = SurfaceSimulation::run_decoder_sweep(mwpm_cfg);

    SurfaceSweepConfig neural_cfg = mwpm_cfg;
    neural_cfg.decoder_name = "neural_mwpm";
    neural_cfg.neural_model_path = "/tmp/lidmas_nonexistent_model.json";
    const auto neural_points = SurfaceSimulation::run_decoder_sweep(neural_cfg);

    if (mwpm_points.size() != neural_points.size()) {
        std::cerr << "[smoke] mwpm vs neural_mwpm output size mismatch\n";
        return false;
    }
    for (size_t i = 0; i < mwpm_points.size(); ++i) {
        if (std::abs(mwpm_points[i].correction_weight_avg - neural_points[i].correction_weight_avg) > 1e-12 ||
            std::abs(mwpm_points[i].logical_fail_rate - neural_points[i].logical_fail_rate) > 1e-12) {
            std::cerr << "[smoke] neural_mwpm fallback mismatch against mwpm at p="
                      << mwpm_points[i].p << "\n";
            return false;
        }
    }

    SurfaceSweepConfig uf_cfg;
    uf_cfg.d = 5;
    uf_cfg.trials = 200;
    uf_cfg.seed_base = 22345;
    uf_cfg.p_values = {0.0, 0.01};
    uf_cfg.decoder_name = "uf";
    uf_cfg.mwpm_graph = "full";

    const auto uf_points = SurfaceSimulation::run_decoder_sweep(uf_cfg);
    if (uf_points.size() < 2) {
        std::cerr << "[smoke] UF sweep did not return expected points\n";
        return false;
    }
    if (!near_zero(uf_points[0].correction_weight_avg)) {
        std::cerr << "[smoke] expected UF correction_weight_avg=0 at p=0, got "
                  << uf_points[0].correction_weight_avg << "\n";
        return false;
    }

    const auto& uf_small = uf_points[1];
    if (uf_small.defect_count_avg > 1e-12) {
        if (!(uf_small.correction_weight_avg > 0.0)) {
            std::cerr << "[smoke] expected UF correction_weight_avg>0 at small p when defects exist\n";
            return false;
        }
        if (std::abs(uf_small.correction_weight_avg - uf_small.defect_count_avg) <= 1e-12) {
            std::cerr << "[smoke] UF correction_weight_avg should not be identically defect_count_avg at small p\n";
            return false;
        }
    }

    SurfaceThresholdConfig thr_cfg;
    thr_cfg.decoder_name = "mwpm";
    thr_cfg.distances = {3};
    thr_cfg.p_start = 0.01;
    thr_cfg.p_end = 0.01;
    thr_cfg.p_step = 0.01;
    thr_cfg.trials = 50;
    thr_cfg.trials_explicit = true;
    thr_cfg.min_trials = 50;
    thr_cfg.max_trials = 50;
    thr_cfg.batch_trials = 50;
    thr_cfg.adaptive_enabled = true;
    thr_cfg.out_csv = "/tmp/lidmas_surface_threshold_smoke.csv";
    thr_cfg.mwpm_graph = "full";
    if (SurfaceThresholdRunner::run(thr_cfg) != 0) {
        std::cerr << "[smoke] surface threshold smoke run failed\n";
        return false;
    }

    SurfaceThresholdConfig scale_cfg;
    scale_cfg.decoder_name = "mwpm";
    scale_cfg.mwpm_graph = "full";
    scale_cfg.distances = {3, 5};
    scale_cfg.p_start = 0.01;
    scale_cfg.p_end = 0.03;
    scale_cfg.p_step = 0.01;
    scale_cfg.trials = 30;
    scale_cfg.trials_explicit = true;
    scale_cfg.adaptive_enabled = false;
    scale_cfg.estimate_threshold = true;
    scale_cfg.scaling_fit = true;
    scale_cfg.scaling_bootstrap = 20;
    scale_cfg.scaling_seed = 12345;
    scale_cfg.grid_pc = 11;
    scale_cfg.grid_nu = 9;
    scale_cfg.pc_min = 0.01;
    scale_cfg.pc_max = 0.03;
    scale_cfg.pc_min_set = true;
    scale_cfg.pc_max_set = true;
    scale_cfg.nu_min = 0.5;
    scale_cfg.nu_max = 2.5;
    scale_cfg.nu_min_set = true;
    scale_cfg.nu_max_set = true;
    scale_cfg.out_csv = "/tmp/lidmas_surface_threshold_scaling_smoke.csv";
    scale_cfg.scaling_report = "/tmp/lidmas_surface_scaling_smoke.md";
    scale_cfg.scaling_json = "/tmp/lidmas_surface_scaling_smoke.json";
    if (SurfaceThresholdRunner::run(scale_cfg) != 0) {
        std::cerr << "[smoke] surface threshold scaling run failed\n";
        return false;
    }
    if (!std::filesystem::exists(scale_cfg.scaling_report)
        || !std::filesystem::exists(scale_cfg.scaling_json)) {
        std::cerr << "[smoke] scaling outputs missing\n";
        return false;
    }
    std::string json;
    if (!readFile(scale_cfg.scaling_json, json)) {
        std::cerr << "[smoke] failed reading scaling JSON output\n";
        return false;
    }
    double pc = 0.0;
    double nu = 0.0;
    if (!extractJsonNumber(json, "pc", pc) || !extractJsonNumber(json, "nu", nu)) {
        std::cerr << "[smoke] failed extracting pc/nu from scaling JSON\n";
        return false;
    }
    if (!(pc >= scale_cfg.pc_min - 1e-9 && pc <= scale_cfg.pc_max + 1e-9)) {
        std::cerr << "[smoke] pc out of requested bounds\n";
        return false;
    }
    if (!(nu >= scale_cfg.nu_min - 1e-9 && nu <= scale_cfg.nu_max + 1e-9)) {
        std::cerr << "[smoke] nu out of requested bounds\n";
        return false;
    }

    {
        HybridEngine hybrid_zero(3, 0.0, 4400001ULL);
        for (int t = 0; t < 16; ++t) {
            hybrid_zero.run_trial();
            const auto& r = hybrid_zero.last_result();
            if (r.decoder_failed || r.logical_failure || r.defect_count != 0 || r.correction_weight != 0) {
                std::cerr << "[smoke] hybrid sigma=0 expected no flips/failures\n";
                return false;
            }
        }
    }

    {
        GaussianNoise noise_hi(5.0, 4400002ULL);
        GKPDigitizer digitizer;
        int flips = 0;
        constexpr int samples = 2000;
        for (int i = 0; i < samples; ++i) {
            const auto [dq, dp] = noise_hi.sample();
            const PauliError pe = digitizer.digitize(dq, dp);
            if (pe.x_flip) flips += 1;
            if (pe.z_flip) flips += 1;
        }
        const double flip_rate = static_cast<double>(flips) / static_cast<double>(2 * samples);
        if (flip_rate < 0.25) {
            std::cerr << "[smoke] hybrid large-sigma flip rate unexpectedly low: "
                      << flip_rate << "\n";
            return false;
        }
    }

    std::cout << "[smoke] PASS\n";
    return true;
}
