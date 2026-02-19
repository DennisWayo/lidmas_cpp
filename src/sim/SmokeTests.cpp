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
#include "surface/MWPMDecoder.h"
#include "surface/SurfaceCode.h"
#include "utils/BSCChannel.h"

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

    std::cout << "[selftest] PASS\n";
    return true;
}
