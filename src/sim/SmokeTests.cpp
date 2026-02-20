#include "sim/SmokeTests.h"

#include <cmath>
#include <iostream>
#include <memory>

#include "codes/LDPCGenerator.h"
#include "decoders/BPDecoderAdapter.h"
#include "graph/TannerGraph.h"
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
        MWPMDecoder mwpm(scode);

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
        MWPMDecoder mwpm(scode);

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

    std::cout << "[selftest] PASS\n";
    return true;
}

bool run_smoke_tests() {
    std::cout << "[smoke] running...\n";

    SurfaceSweepConfig cfg;
    cfg.d = 3;
    cfg.trials = 100;
    cfg.seed_base = 12345;
    cfg.p_values = {0.0};
    cfg.decoder_name = "mwpm";

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
    if (SurfaceThresholdRunner::run(thr_cfg) != 0) {
        std::cerr << "[smoke] surface threshold smoke run failed\n";
        return false;
    }

    std::cout << "[smoke] PASS\n";
    return true;
}
