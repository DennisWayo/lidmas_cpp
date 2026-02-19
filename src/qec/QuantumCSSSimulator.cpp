#include "qec/QuantumCSSSimulator.h"
#include "qec/CSSSyndrome.h"
#include "qec/PauliChannel.h"
#include <algorithm>
#include <cmath>
#include <random>
#include <stdexcept>

namespace {

std::vector<int> xorBinary(const std::vector<int>& a,
                           const std::vector<int>& b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("xorBinary requires equal-sized vectors");
    }
    std::vector<int> out(a.size(), 0);
    for (size_t i = 0; i < a.size(); ++i) {
        out[i] = (a[i] ^ b[i]) & 1;
    }
    return out;
}

} // namespace

QuantumCSSSimulator::QuantumCSSSimulator(const BinaryMatrix& Hx,
                                         const BinaryMatrix& Hz,
                                         BeliefPropagation::Params bp_params)
    : hx_(Hx),
      hz_(Hz),
      gx_(hx_),
      gz_(hz_),
      bp_params_(bp_params) {
    if (hx_.cols() != hz_.cols()) {
        throw std::invalid_argument("QuantumCSSSimulator expects Hx and Hz with equal column count");
    }
}

bool QuantumCSSSimulator::isZeroSyndrome(const std::vector<int>& s) {
    for (int v : s) {
        if ((v & 1) != 0) return false;
    }
    return true;
}

QuantumCSSSimulator::QECStats QuantumCSSSimulator::run(const RunConfig& cfg,
                                                       const LogicalPair* logicals) const {
    const int n = hx_.cols();
    if (cfg.trials <= 0) {
        return {};
    }

    long long fail_x_log = 0;
    long long fail_z_log = 0;
    long long fail_any_log = 0;
    long long parity_ok_x = 0;
    long long parity_ok_z = 0;
    long long iters_x = 0;
    long long iters_z = 0;
    long long max_hit_x = 0;
    long long max_hit_z = 0;

    const double pX_eff = (cfg.noise_model == NoiseModel::DEPOLARIZING)
        ? std::clamp((2.0 / 3.0) * cfg.p, 0.0, 0.499999)
        : std::clamp(cfg.pX, 0.0, 0.499999);
    const double pZ_eff = (cfg.noise_model == NoiseModel::DEPOLARIZING)
        ? std::clamp((2.0 / 3.0) * cfg.p, 0.0, 0.499999)
        : std::clamp(cfg.pZ, 0.0, 0.499999);

    const int p_key = (cfg.noise_model == NoiseModel::DEPOLARIZING)
        ? static_cast<int>(std::llround(cfg.p * 1e6))
        : static_cast<int>(std::llround(cfg.pX * 1e6) + 17.0 * std::llround(cfg.pZ * 1e6));

    BeliefPropagation dec_x(gz_, bp_params_); // decode eX from sX using Hz
    BeliefPropagation dec_z(gx_, bp_params_); // decode eZ from sZ using Hx
    const std::vector<int> erasures(n, 0);

    for (int t = 0; t < cfg.trials; ++t) {
        std::mt19937 rng(static_cast<uint32_t>(cfg.seed_base + p_key + t));
        PauliSample sample = (cfg.noise_model == NoiseModel::DEPOLARIZING)
            ? PauliChannel::sampleDepolarizing(n, cfg.p, rng)
            : PauliChannel::sampleIndependentXZ(n, cfg.pX, cfg.pZ, rng);

        // CSS convention:
        // sX = Hz * eX (X errors detected by Z stabilizers)
        // sZ = Hx * eZ (Z errors detected by X stabilizers)
        const std::vector<int> sX = computeSyndrome(hz_, sample.eX);
        const std::vector<int> sZ = computeSyndrome(hx_, sample.eZ);

        const std::vector<int> x_hat = dec_x.decode(sX, erasures, pX_eff);
        const std::vector<int> z_hat = dec_z.decode(sZ, erasures, pZ_eff);

        iters_x += dec_x.lastIterations();
        iters_z += dec_z.lastIterations();
        if (dec_x.lastHitMaxIters()) max_hit_x++;
        if (dec_z.lastHitMaxIters()) max_hit_z++;

        const std::vector<int> rX = xorBinary(sample.eX, x_hat);
        const std::vector<int> rZ = xorBinary(sample.eZ, z_hat);

        if (isZeroSyndrome(computeSyndrome(hz_, rX))) parity_ok_x++;
        if (isZeroSyndrome(computeSyndrome(hx_, rZ))) parity_ok_z++;

        bool x_fail = false;
        bool z_fail = false;
        if (logicals != nullptr) {
            x_fail = hasLogicalXFailure(rZ, *logicals);
            z_fail = hasLogicalZFailure(rX, *logicals);
        }

        if (x_fail) fail_x_log++;
        if (z_fail) fail_z_log++;
        if (x_fail || z_fail) fail_any_log++;
    }

    QECStats out;
    const double denom = static_cast<double>(cfg.trials);
    out.logical_X_fail_rate = fail_x_log / denom;
    out.logical_Z_fail_rate = fail_z_log / denom;
    out.logical_total_fail_rate = fail_any_log / denom;
    out.avg_iter_X = iters_x / denom;
    out.avg_iter_Z = iters_z / denom;
    out.max_iter_hit_rate_X = max_hit_x / denom;
    out.max_iter_hit_rate_Z = max_hit_z / denom;
    out.parity_sat_rate_X = parity_ok_x / denom;
    out.parity_sat_rate_Z = parity_ok_z / denom;
    return out;
}
