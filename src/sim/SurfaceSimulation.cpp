#include "sim/SurfaceSimulation.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iostream>
#include <memory>
#include <random>
#include <stdexcept>

#include "core/DecoderConfig.h"
#include "core/PluginRegistry.h"
#include "core/RegisterPlugins.h"
#include "cv/gaussian_noise.hpp"
#include "gkp/gkp_digitizer.hpp"
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

using SparseRows = std::vector<std::vector<int>>;

SparseRows buildSparseRows(const BinaryMatrix& H) {
    SparseRows rows(static_cast<size_t>(H.rows()));
    for (int r = 0; r < H.rows(); ++r) {
        auto& row = rows[static_cast<size_t>(r)];
        row.reserve(static_cast<size_t>(H.cols() / 8 + 1));
        for (int c = 0; c < H.cols(); ++c) {
            if ((H.get(r, c) & 1) != 0) row.push_back(c);
        }
    }
    return rows;
}

struct GKPNoiseConfig {
    double gate_error = 0.0;
    double meas_error = 0.0;
    double idle_error = 0.0;
    double loss_prob = 0.0;
    std::vector<double> loss_map;
};

struct GkpTrialSample {
    std::vector<int> ex;
    std::vector<int> ez;
    std::vector<int> sx;
    std::vector<int> sz;
};

int randomBit(std::mt19937_64& rng) {
    std::uniform_int_distribution<int> dist(0, 1);
    return dist(rng);
}

GkpTrialSample sampleGkp(const SurfaceCode& code,
                         const SparseRows& hx_rows,
                         const SparseRows& hz_rows,
                         double sigma,
                         const GKPNoiseConfig& noise_cfg,
                         uint64_t seed) {
    GkpTrialSample out;
    const int n = code.n();
    out.ex.assign(static_cast<size_t>(n), 0);
    out.ez.assign(static_cast<size_t>(n), 0);

    GaussianNoise noise(sigma, seed);
    GKPDigitizer digitizer;
    std::mt19937_64 rng(seed ^ 0x9e3779b97f4a7c15ULL);
    std::bernoulli_distribution gate_flip(std::clamp(noise_cfg.gate_error, 0.0, 1.0));
    std::bernoulli_distribution idle_flip(std::clamp(noise_cfg.idle_error, 0.0, 1.0));

    for (int q = 0; q < n; ++q) {
        const auto [dq, dp] = noise.sample();
        const PauliError e = digitizer.digitize(dq, dp);
        int ex = e.x_flip ? 1 : 0;
        int ez = e.z_flip ? 1 : 0;

        if (gate_flip(rng)) ex ^= 1;
        if (gate_flip(rng)) ez ^= 1;
        if (idle_flip(rng)) ex ^= 1;
        if (idle_flip(rng)) ez ^= 1;

        double loss_p = noise_cfg.loss_prob;
        if (!noise_cfg.loss_map.empty()) {
            loss_p = noise_cfg.loss_map[static_cast<size_t>(q)];
        }
        if (loss_p > 0.0) {
            std::bernoulli_distribution loss_flip(std::clamp(loss_p, 0.0, 1.0));
            if (loss_flip(rng)) {
                ex = randomBit(rng);
                ez = randomBit(rng);
            }
        }

        out.ex[static_cast<size_t>(q)] = ex;
        out.ez[static_cast<size_t>(q)] = ez;
    }

    out.sx.assign(hx_rows.size(), 0);
    for (size_t r = 0; r < hx_rows.size(); ++r) {
        int parity = 0;
        for (int c : hx_rows[r]) parity ^= (out.ez[static_cast<size_t>(c)] & 1);
        out.sx[r] = parity & 1;
    }

    out.sz.assign(hz_rows.size(), 0);
    for (size_t r = 0; r < hz_rows.size(); ++r) {
        int parity = 0;
        for (int c : hz_rows[r]) parity ^= (out.ex[static_cast<size_t>(c)] & 1);
        out.sz[r] = parity & 1;
    }

    const double meas_p = std::clamp(noise_cfg.meas_error, 0.0, 1.0);
    if (meas_p > 0.0) {
        std::bernoulli_distribution meas_flip(meas_p);
        for (int& v : out.sx) v ^= meas_flip(rng) ? 1 : 0;
        for (int& v : out.sz) v ^= meas_flip(rng) ? 1 : 0;
    }

    return out;
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
    std::string mwpm_graph = cfg.mwpm_graph;
    if (mwpm_graph != "full" && mwpm_graph != "simple") {
        mwpm_graph = "full";
    }

    DecoderConfig dec_cfg;
    dec_cfg.decoder_name = decoder_name;
    dec_cfg.distance = cfg.d;
    dec_cfg.trials = cfg.trials;
    dec_cfg.seed = cfg.seed_base;
    dec_cfg.alpha = cfg.bp_alpha;
    dec_cfg.string_params["decoder_name"] = decoder_name;
    dec_cfg.string_params["bp_mode"] =
        (cfg.bp_mode == BeliefPropagation::Mode::NORMALIZED_MIN_SUM) ? "nms" : "sum-product";
    dec_cfg.string_params["weight_mode"] = cfg.weight_mode;
    dec_cfg.string_params["mwpm_graph"] = mwpm_graph;
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

    const bool sigma_mode = (cfg.mode != SurfaceNoiseMode::Pauli);
    const std::vector<double>& sweep_values = sigma_mode ? cfg.sigma_values : cfg.p_values;
    if (sweep_values.empty()) {
        throw std::runtime_error("Surface sweep requires non-empty p_values or sigma_values");
    }

    const SparseRows hx_rows = buildSparseRows(code.Hx());
    const SparseRows hz_rows = buildSparseRows(code.Hz());
    GKPNoiseConfig gkp_cfg{cfg.gkp_gate_error, cfg.gkp_meas_error, cfg.gkp_idle_error,
                           cfg.gkp_loss_prob, cfg.gkp_loss_map};
    if (cfg.mode == SurfaceNoiseMode::GKP && !gkp_cfg.loss_map.empty()
        && static_cast<int>(gkp_cfg.loss_map.size()) != code.n()) {
        throw std::runtime_error("gkp_loss_map size must match code.n()");
    }

    std::vector<SurfaceStubPointStats> out;
    out.reserve(sweep_values.size());

    bool warned_decode = false;
    for (double sweep : sweep_values) {
        long long defect_sum = 0;
        long long correction_weight_sum = 0;
        long long logical_fail_sum = 0;
        const int sweep_key = static_cast<int>(std::llround(sweep * 1e6));
        const double p = sigma_mode ? 0.0 : sweep;
        const double sigma = sigma_mode ? sweep : 0.0;

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
            const uint64_t seed = cfg.seed_base + static_cast<uint64_t>(sweep_key + t);
            if (cfg.mode == SurfaceNoiseMode::GKP) {
                const GkpTrialSample sample = sampleGkp(code, hx_rows, hz_rows, sigma, gkp_cfg, seed);
                for (int v : sample.sx) defect_sum += (v & 1);
                for (int v : sample.sz) defect_sum += (v & 1);

                try {
                    SurfaceSyndrome syn_x;
                    syn_x.sz = sample.sz;
                    const SurfaceCorrection corr_x = surf_plugin->decode(syn_x, code);
                    SurfaceSyndrome syn_z;
                    syn_z.sx = sample.sx;
                    const SurfaceCorrection corr_z = surf_plugin->decode(syn_z, code);

                    correction_weight_sum += SurfacePipeline::correctionWeight(corr_x, code.n());
                    correction_weight_sum += SurfacePipeline::correctionWeight(corr_z, code.n());

                    const std::vector<int> residual_ex =
                        SurfacePipeline::applyCorrection(sample.ex, corr_x, code.n());
                    const std::vector<int> residual_ez =
                        SurfacePipeline::applyCorrection(sample.ez, corr_z, code.n());

                    const bool logical_fail =
                        (dot_mod2(residual_ex, code.logicalXSupport()) != 0) ||
                        (dot_mod2(residual_ez, code.logicalZSupport()) != 0);
                    if (logical_fail) logical_fail_sum++;
                } catch (const std::exception& ex) {
                    if (!warned_decode) {
                        std::cerr << "WARNING: surface demo decode error: " << ex.what() << "\n";
                        warned_decode = true;
                    }
                    logical_fail_sum++;
                } catch (...) {
                    if (!warned_decode) {
                        std::cerr << "WARNING: surface demo decode error: unknown exception\n";
                        warned_decode = true;
                    }
                    logical_fail_sum++;
                }
            } else if (cfg.mode == SurfaceNoiseMode::Hybrid) {
                throw std::runtime_error("surface demo does not support hybrid mode");
            } else {
                const auto syn = SurfaceSyndrome::sample(code, p, p, seed);
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
        }

        SurfaceStubPointStats s;
        s.p = sweep;
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
