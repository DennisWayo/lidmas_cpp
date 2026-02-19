#include "sim/SurfaceSimulation.h"

#include <cmath>
#include <memory>

#include "core/DecoderConfig.h"
#include "core/DecoderRegistry.h"
#include "core/RegisterDecoders.h"
#include "qec/LogicalOperators.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfacePipeline.h"
#include "surface/SurfaceSyndrome.h"

namespace {

std::vector<SurfaceStubPointStats> run_surface_sweep(const SurfaceStubSweepConfig& cfg) {
    SurfaceCode code(cfg.d);
    SurfacePipeline pipeline(code);

    DecoderRegistry registry;
    registerBuiltInDecoders(registry);

    DecoderConfig dec_cfg;
    dec_cfg.ptr_params["surface_code"] = &code;
    const std::string decoder_name = cfg.decoder_name.empty() ? "mwpm_stub" : cfg.decoder_name;
    std::unique_ptr<IDecoder> decoder = registry.create(decoder_name, dec_cfg);

    std::vector<SurfaceStubPointStats> out;
    out.reserve(cfg.p_values.size());

    for (double p : cfg.p_values) {
        long long defect_sum = 0;
        long long correction_weight_sum = 0;
        long long logical_fail_sum = 0;
        const int p_key = static_cast<int>(std::llround(p * 1e6));

        for (int t = 0; t < cfg.trials; ++t) {
            const auto syn = SurfaceSyndrome::sample(
                code, p, p, cfg.seed_base + static_cast<uint64_t>(p_key + t));
            const MatchingProblem mp = pipeline.buildMatchingProblemFromSz(syn.sz);
            defect_sum += mp.numDefects();

            DecodeRequest req;
            req.syndrome = &syn.sz;
            req.p_error = p;
            const DecodeResult dec = decoder->decode(req);

            int corr_weight = 0;
            for (int bit : dec.correction) corr_weight += (bit & 1);
            correction_weight_sum += corr_weight;

            std::vector<int> residual_ex(code.n(), 0);
            for (int i = 0; i < code.n(); ++i) {
                const int corr_bit = (i < static_cast<int>(dec.correction.size())) ? (dec.correction[i] & 1) : 0;
                residual_ex[i] = (syn.ex[i] ^ corr_bit) & 1;
            }

            const bool logical_fail =
                (dot_mod2(residual_ex, code.logicalXSupport()) != 0) ||
                (dot_mod2(residual_ex, code.logicalZSupport()) != 0);
            if (logical_fail) logical_fail_sum++;
        }

        SurfaceStubPointStats s;
        s.p = p;
        const double denom = static_cast<double>(cfg.trials);
        s.defect_count_avg = defect_sum / denom;
        s.correction_weight_avg = correction_weight_sum / denom;
        s.logical_fail_rate = logical_fail_sum / denom;
        out.push_back(s);
    }

    return out;
}

} // namespace

std::vector<SurfaceStubPointStats> SurfaceSimulation::run_stub_sweep(const SurfaceStubSweepConfig& cfg) {
    SurfaceStubSweepConfig cfg_local = cfg;
    cfg_local.decoder_name = "mwpm_stub";
    return run_surface_sweep(cfg_local);
}

std::vector<SurfaceStubPointStats> SurfaceSimulation::run_mwpm_sweep(const SurfaceStubSweepConfig& cfg) {
    SurfaceStubSweepConfig cfg_local = cfg;
    cfg_local.decoder_name = "mwpm";
    return run_surface_sweep(cfg_local);
}
