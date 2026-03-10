#include "decoder_io/SurfaceDecoderAdapter.h"

#include <algorithm>
#include <sstream>
#include <stdexcept>

#include "core/PluginRegistry.h"
#include "surface/SurfaceSyndrome.h"

namespace decoder_io {

SurfaceDecoderAdapter::SurfaceDecoderAdapter(const SurfaceDecoderAdapterConfig& cfg,
                                             const PluginRegistry& reg)
    : cfg_(cfg),
      code_(cfg.distance) {
    plugin_base_ = reg.create(cfg_.decoder_name);
    surf_plugin_ = dynamic_cast<ISurfaceDecoderPlugin*>(plugin_base_.get());
    if (surf_plugin_ == nullptr) {
        throw std::runtime_error("decoder is not a surface plugin: " + cfg_.decoder_name);
    }
}

DecoderConfig SurfaceDecoderAdapter::buildDecoderConfig(const DecodeRequest& request) const {
    DecoderConfig dec_cfg;
    dec_cfg.decoder_name = cfg_.decoder_name;
    dec_cfg.distance = cfg_.distance;
    dec_cfg.seed = cfg_.seed;
    dec_cfg.p = cfg_.default_p;

    if (request.noise.gate_error_rate > 0.0) {
        dec_cfg.p = request.noise.gate_error_rate;
    }

    dec_cfg.string_params["decoder_name"] = cfg_.decoder_name;
    dec_cfg.string_params["weight_mode"] = cfg_.weight_mode;
    dec_cfg.string_params["mwpm_graph"] = cfg_.mwpm_graph;
    dec_cfg.string_params["neural_model"] = cfg_.neural_model_path;
    dec_cfg.string_params["neural_weights"] =
        cfg_.neural_weights_path.empty() ? cfg_.neural_model_path : cfg_.neural_weights_path;
    dec_cfg.int_params["distance"] = cfg_.distance;
    dec_cfg.int_params["seed"] = static_cast<int>(cfg_.seed & 0x7fffffffULL);
    const bool weighted = cfg_.uf_weighted || cfg_.weight_mode == "neural" || cfg_.weight_mode == "llr";
    dec_cfg.int_params["uf_weighted"] = weighted ? 1 : 0;
    dec_cfg.ptr_params["surface_code"] = &code_;

    double llr_p_data = (cfg_.llr_p_data >= 0.0) ? cfg_.llr_p_data : dec_cfg.p;
    double llr_p_meas = (cfg_.llr_p_meas >= 0.0) ? cfg_.llr_p_meas : dec_cfg.p;
    double llr_p_idle = (cfg_.llr_p_idle >= 0.0) ? cfg_.llr_p_idle : dec_cfg.p;
    if (request.noise.gate_error_rate > 0.0) llr_p_data = request.noise.gate_error_rate;
    if (request.noise.meas_error_rate > 0.0) llr_p_meas = request.noise.meas_error_rate;
    if (request.noise.idle_error_rate > 0.0) llr_p_idle = request.noise.idle_error_rate;

    dec_cfg.double_params["llr_p_data"] = llr_p_data;
    dec_cfg.double_params["llr_p_meas"] = llr_p_meas;
    dec_cfg.double_params["llr_p_idle"] = llr_p_idle;
    dec_cfg.double_params["llr_clamp_min"] = cfg_.llr_clamp_min;
    dec_cfg.double_params["llr_clamp_max"] = cfg_.llr_clamp_max;
    dec_cfg.double_params["mwpm_weight_scale"] = cfg_.mwpm_weight_scale;

    return dec_cfg;
}

void SurfaceDecoderAdapter::appendUnique(const std::vector<int>& src, std::vector<int>& dst) {
    for (int v : src) {
        if (std::find(dst.begin(), dst.end(), v) == dst.end()) {
            dst.push_back(v);
        }
    }
}

int SurfaceDecoderAdapter::countOnes(const std::vector<int>& v) {
    int count = 0;
    for (int bit : v) count += (bit & 1);
    return count;
}

void SurfaceDecoderAdapter::applyDense(const SyndromeDense& dense, std::vector<int>& dest) {
    const int n_bits = std::min(dense.n_bits, static_cast<int>(dest.size()));
    for (int i = 0; i < n_bits; ++i) {
        const size_t byte_idx = static_cast<size_t>(i / 8);
        const int bit_idx = i % 8;
        if (byte_idx >= dense.bits.size()) continue;
        const bool bit = ((dense.bits[byte_idx] >> bit_idx) & 0x1u) != 0;
        if (bit) dest[static_cast<size_t>(i)] ^= 1;
    }
}

DecodeResponse SurfaceDecoderAdapter::decode(const DecodeRequest& request) {
    DecodeResponse resp;
    resp.correction.decoder_name = cfg_.decoder_name;

    if (surf_plugin_ == nullptr) {
        resp.diagnostics["error"] = "decoder plugin unavailable";
        return resp;
    }

    const int sx_size = code_.Hx().rows();
    const int sz_size = code_.Hz().rows();
    std::vector<int> sx(static_cast<size_t>(std::max(0, sx_size)), 0);
    std::vector<int> sz(static_cast<size_t>(std::max(0, sz_size)), 0);

    bool seen_x = false;
    bool seen_z = false;
    int out_of_range = 0;
    int unknown_types = 0;

    for (const auto& dense : request.dense) {
        if (dense.type == SyndromeType::X) {
            applyDense(dense, sx);
            seen_x = true;
        } else if (dense.type == SyndromeType::Z) {
            applyDense(dense, sz);
            seen_z = true;
        } else {
            unknown_types += 1;
        }
    }

    for (const auto& ev : request.events) {
        if (ev.type == SyndromeType::X) {
            if (ev.index >= 0 && ev.index < sx_size) {
                sx[static_cast<size_t>(ev.index)] ^= 1;
                seen_x = true;
            } else {
                out_of_range += 1;
            }
        } else if (ev.type == SyndromeType::Z) {
            if (ev.index >= 0 && ev.index < sz_size) {
                sz[static_cast<size_t>(ev.index)] ^= 1;
                seen_z = true;
            } else {
                out_of_range += 1;
            }
        } else {
            unknown_types += 1;
        }
    }

    if (unknown_types > 0) {
        resp.diagnostics["unknown_syndrome_type"] = std::to_string(unknown_types);
    }
    if (out_of_range > 0) {
        resp.diagnostics["out_of_range_events"] = std::to_string(out_of_range);
    }
    if (request.n_qubits > 0 && request.n_qubits != code_.n()) {
        resp.diagnostics["n_qubits_mismatch"] =
            std::to_string(request.n_qubits) + " vs " + std::to_string(code_.n());
    }

    DecoderConfig dec_cfg = buildDecoderConfig(request);
    surf_plugin_->configure(dec_cfg);

    if (seen_z) {
        SurfaceSyndrome syn;
        syn.sz = sz;
        const SurfaceCorrection corr_x = surf_plugin_->decode(syn, code_);
        resp.correction.qubit_flips_x = corr_x.qubit_flips;
    }
    if (seen_x) {
        SurfaceSyndrome syn;
        syn.sx = sx;
        const SurfaceCorrection corr_z = surf_plugin_->decode(syn, code_);
        resp.correction.qubit_flips_z = corr_z.qubit_flips;
    }

    appendUnique(resp.correction.qubit_flips_x, resp.correction.qubit_flips);
    appendUnique(resp.correction.qubit_flips_z, resp.correction.qubit_flips);

    resp.diagnostics["sx_count"] = std::to_string(countOnes(sx));
    resp.diagnostics["sz_count"] = std::to_string(countOnes(sz));
    resp.diagnostics["sx_present"] = seen_x ? "1" : "0";
    resp.diagnostics["sz_present"] = seen_z ? "1" : "0";
    if (!seen_x && !seen_z) {
        resp.diagnostics["warning"] = "no_syndrome_bits";
    }
    if (!request.code_id.empty()) {
        resp.diagnostics["code_id"] = request.code_id;
    }
    if (request.noise.sigma > 0.0) {
        std::ostringstream oss;
        oss << request.noise.sigma;
        resp.diagnostics["sigma"] = oss.str();
    }

    return resp;
}

} // namespace decoder_io
