#include "qec/QuantumCSSSimulator.h"
#include "qec/CSSSyndrome.h"
#include "utils/SeedUtils.h"
#include "utils/SyndromeUtils.h"
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
                                         const std::function<std::unique_ptr<IDecoder>()>& x_decoder_factory,
                                         const std::function<std::unique_ptr<IDecoder>()>& z_decoder_factory,
                                         IQECChannel& channel)
    : hx_(Hx),
      hz_(Hz),
      x_decoder_factory_(x_decoder_factory),
      z_decoder_factory_(z_decoder_factory),
      channel_(channel) {
    if (hx_.cols() != hz_.cols()) {
        throw std::invalid_argument("QuantumCSSSimulator expects Hx and Hz with equal column count");
    }
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

    const double pX_eff = (cfg.noise_model == QECNoiseModel::DEPOLARIZING)
        ? std::clamp((2.0 / 3.0) * cfg.p, 0.0, 0.499999)
        : std::clamp(cfg.pX, 0.0, 0.499999);
    const double pZ_eff = (cfg.noise_model == QECNoiseModel::DEPOLARIZING)
        ? std::clamp((2.0 / 3.0) * cfg.p, 0.0, 0.499999)
        : std::clamp(cfg.pZ, 0.0, 0.499999);

    const int p_key = (cfg.noise_model == QECNoiseModel::DEPOLARIZING)
        ? qec_p_key_depolarizing(cfg.p)
        : qec_p_key_independent(cfg.pX, cfg.pZ);

    auto dec_x = x_decoder_factory_();
    auto dec_z = z_decoder_factory_();
    const std::vector<int> erasures(n, 0);

    for (int t = 0; t < cfg.trials; ++t) {
        std::mt19937 rng(qec_trial_seed(cfg.seed_base, p_key, t));
        const QECSample sample = channel_.sample(
            rng, n, cfg.noise_model, cfg.pX, cfg.pZ, cfg.p);

        // CSS convention:
        // sX = Hz * eX (X errors detected by Z stabilizers)
        // sZ = Hx * eZ (Z errors detected by X stabilizers)
        const std::vector<int> sX = computeSyndrome(hz_, sample.eX);
        const std::vector<int> sZ = computeSyndrome(hx_, sample.eZ);

        DecodeRequest req_x;
        req_x.syndrome = &sX;
        req_x.erasures = &erasures;
        req_x.p_error = pX_eff;
        const DecodeResult res_x = dec_x->decode(req_x);

        DecodeRequest req_z;
        req_z.syndrome = &sZ;
        req_z.erasures = &erasures;
        req_z.p_error = pZ_eff;
        const DecodeResult res_z = dec_z->decode(req_z);

        const std::vector<int>& x_hat = res_x.correction;
        const std::vector<int>& z_hat = res_z.correction;

        iters_x += res_x.iters;
        iters_z += res_z.iters;
        if (res_x.hit_max_iters) max_hit_x++;
        if (res_z.hit_max_iters) max_hit_z++;

        const std::vector<int> rX = xorBinary(sample.eX, x_hat);
        const std::vector<int> rZ = xorBinary(sample.eZ, z_hat);

        if (parity_satisfied(hz_, rX)) parity_ok_x++;
        if (parity_satisfied(hx_, rZ)) parity_ok_z++;

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
