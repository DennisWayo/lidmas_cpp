#include "sim/SurfaceSimulation.h"

#include <chrono>
#include <cmath>
#include <memory>
#include <stdexcept>

#include "core/DecoderConfig.h"
#include "core/PluginRegistry.h"
#include "core/RegisterPlugins.h"
#include "qec/LogicalOperators.h"
#include "surface/ISurfaceDecoderPlugin.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfacePipeline.h"
#include "surface/SurfaceSyndrome.h"

namespace {

std::string normalizeSurfaceDecoderName(const std::string& name) {
    if (name.empty()) return "stub";
    if (name == "stub" || name == "mwpm_stub") return "stub";
    if (name == "mwpm") return "mwpm";
    if (name == "uf") return "uf";
    if (name == "neural_mwpm") return "neural_mwpm";
    return name;
}

std::vector<SurfaceStubPointStats> run_surface_sweep(const SurfaceSweepConfig& cfg,
                                                     const PluginRegistry* reg_in) {
    SurfaceCode code(cfg.d);
    SurfacePipeline pipeline(code);

    PluginRegistry local_registry;
    const PluginRegistry* registry = reg_in;
    if (registry == nullptr) {
        RegisterAllPlugins(local_registry);
        registry = &local_registry;
    }

    const std::string decoder_name = normalizeSurfaceDecoderName(cfg.decoder_name);

    DecoderConfig dec_cfg;
    dec_cfg.decoder_name = decoder_name;
    dec_cfg.distance = cfg.d;
    dec_cfg.trials = cfg.trials;
    dec_cfg.seed = cfg.seed_base;
    dec_cfg.string_params["decoder_name"] = decoder_name;
    dec_cfg.string_params["weight_mode"] = cfg.weight_mode;
    dec_cfg.string_params["neural_model"] = cfg.neural_model_path;
    dec_cfg.string_params["neural_weights"] =
        cfg.neural_weights_path.empty() ? cfg.neural_model_path : cfg.neural_weights_path;
    dec_cfg.int_params["distance"] = cfg.d;
    dec_cfg.int_params["trials"] = cfg.trials;
    dec_cfg.int_params["seed"] = static_cast<int>(cfg.seed_base & 0x7fffffffULL);
    dec_cfg.int_params["uf_weighted"] =
        (cfg.uf_weighted || cfg.weight_mode == "neural" || cfg.weight_mode == "llr") ? 1 : 0;
    dec_cfg.ptr_params["surface_code"] = &code;

    std::unique_ptr<IDecoderPlugin> plugin_base = registry->create(decoder_name);
    auto* surf_plugin = dynamic_cast<ISurfaceDecoderPlugin*>(plugin_base.get());
    if (surf_plugin == nullptr) {
        throw std::runtime_error("Selected plugin is not a surface decoder: " + decoder_name);
    }

    std::vector<SurfaceStubPointStats> out;
    out.reserve(cfg.p_values.size());

    for (double p : cfg.p_values) {
        long long defect_sum = 0;
        long long correction_weight_sum = 0;
        long long logical_fail_sum = 0;
        const int p_key = static_cast<int>(std::llround(p * 1e6));
        dec_cfg.p = p;
        dec_cfg.double_params["llr_p_data"] = (cfg.llr_p_data >= 0.0) ? cfg.llr_p_data : p;
        dec_cfg.double_params["llr_p_meas"] = (cfg.llr_p_meas >= 0.0) ? cfg.llr_p_meas : p;
        dec_cfg.double_params["llr_p_idle"] = (cfg.llr_p_idle >= 0.0) ? cfg.llr_p_idle : p;
        dec_cfg.double_params["llr_clamp_min"] = cfg.llr_clamp_min;
        dec_cfg.double_params["llr_clamp_max"] = cfg.llr_clamp_max;
        dec_cfg.double_params["mwpm_weight_scale"] = cfg.mwpm_weight_scale;
        const auto point_start = std::chrono::steady_clock::now();
        surf_plugin->configure(dec_cfg);

        for (int t = 0; t < cfg.trials; ++t) {
            const auto syn = SurfaceSyndrome::sample(
                code, p, p, cfg.seed_base + static_cast<uint64_t>(p_key + t));
            const MatchingProblem mp = pipeline.buildMatchingProblemFromSz(syn.sz);
            defect_sum += mp.numDefects();

            // Keep surface demo behavior identical: decode against sz only.
            SurfaceSyndrome decode_syn;
            decode_syn.sz = syn.sz;
            const SurfaceCorrection corr = surf_plugin->decode(decode_syn, code);

            correction_weight_sum += SurfacePipeline::correctionWeight(corr, code.n());
            const std::vector<int> residual_ex = SurfacePipeline::applyCorrection(syn.ex, corr, code.n());

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
        const auto point_end = std::chrono::steady_clock::now();
        const double elapsed_ms = std::chrono::duration<double, std::milli>(point_end - point_start).count();
        s.avg_runtime_ms = elapsed_ms / denom;
        out.push_back(s);
    }

    return out;
}

} // namespace

std::vector<SurfaceStubPointStats> SurfaceSimulation::run_decoder_sweep(const SurfaceSweepConfig& cfg) {
    return run_surface_sweep(cfg, nullptr);
}

std::vector<SurfaceStubPointStats> SurfaceSimulation::run_decoder_sweep(const SurfaceSweepConfig& cfg,
                                                                        const PluginRegistry& reg) {
    return run_surface_sweep(cfg, &reg);
}

std::vector<SurfaceStubPointStats> SurfaceSimulation::run_stub_sweep(const SurfaceSweepConfig& cfg) {
    SurfaceSweepConfig cfg_local = cfg;
    cfg_local.decoder_name = "stub";
    return run_surface_sweep(cfg_local, nullptr);
}

std::vector<SurfaceStubPointStats> SurfaceSimulation::run_mwpm_sweep(const SurfaceSweepConfig& cfg) {
    SurfaceSweepConfig cfg_local = cfg;
    cfg_local.decoder_name = "mwpm";
    return run_surface_sweep(cfg_local, nullptr);
}
