#include "plugins/mwpm/MWPMPlugin.h"

#include <algorithm>
#include <memory>
#include <string>

#include "LLRWeightField.h"
#include "NeuralWeightField.h"
#include "UniformWeightField.h"
#include "surface/MWPMDecoder.h"

namespace {

SurfaceCorrection bitmaskToCorrection(const std::vector<int>& bitmask) {
    SurfaceCorrection corr;
    corr.qubit_flips.reserve(bitmask.size());
    for (int i = 0; i < static_cast<int>(bitmask.size()); ++i) {
        if ((bitmask[i] & 1) != 0) corr.qubit_flips.push_back(i);
    }
    corr.weight = static_cast<int>(corr.qubit_flips.size());
    return corr;
}

} // namespace

std::string MWPMPlugin::name() const {
    return "mwpm";
}

std::string MWPMPlugin::family() const {
    return "surface";
}

void MWPMPlugin::configure(const DecoderConfig& cfg) {
    cfg_ = cfg;
}

SurfaceCorrection MWPMPlugin::decode(const SurfaceSyndrome& syn, const SurfaceCode& code) {
    auto getDoubleParam = [&](const std::string& key, double fallback) {
        const auto it = cfg_.double_params.find(key);
        return (it == cfg_.double_params.end()) ? fallback : it->second;
    };

    std::string weight_mode = "uniform";
    const auto wmode_it = cfg_.string_params.find("weight_mode");
    if (wmode_it != cfg_.string_params.end() && !wmode_it->second.empty()) {
        weight_mode = wmode_it->second;
    }
    if (weight_mode != "uniform" && weight_mode != "neural" && weight_mode != "llr") {
        weight_mode = "uniform";
    }

    const double p_error = cfg_.p;
    const uint64_t seed = cfg_.seed;
    const double mwpm_weight_scale = std::max(1.0, getDoubleParam("mwpm_weight_scale", 1000.0));

    const double llr_p_data = getDoubleParam("llr_p_data", p_error);
    const double llr_p_meas = getDoubleParam("llr_p_meas", p_error);
    const double llr_p_idle = getDoubleParam("llr_p_idle", p_error);
    const double llr_clamp_min = getDoubleParam("llr_clamp_min", 1e-12);
    const double llr_clamp_max = getDoubleParam("llr_clamp_max", 1.0 - 1e-12);

    const bool rebuild =
        (cached_decoder_ == nullptr)
        || (cached_code_ != &code)
        || (cached_weight_mode_ != weight_mode)
        || (cached_p_error_ != p_error)
        || (cached_seed_ != seed)
        || (cached_weight_scale_ != mwpm_weight_scale)
        || (cached_llr_p_data_ != llr_p_data)
        || (cached_llr_p_meas_ != llr_p_meas)
        || (cached_llr_p_idle_ != llr_p_idle)
        || (cached_llr_clamp_min_ != llr_clamp_min)
        || (cached_llr_clamp_max_ != llr_clamp_max);

    if (rebuild) {
        if (weight_mode == "uniform") {
            cached_weight_field_.reset();
            cached_decoder_ = std::make_unique<MWPMDecoder>(code);
        } else if (weight_mode == "neural") {
            cached_weight_field_ = std::make_unique<NeuralWeightField>(
                code.lattice().distance(), p_error, seed);
            cached_decoder_ = std::make_unique<MWPMDecoder>(
                code, cached_weight_field_.get(), mwpm_weight_scale);
        } else {
            cached_weight_field_ = std::make_unique<LLRWeightField>(
                llr_p_data, llr_p_meas, llr_p_idle, llr_clamp_min, llr_clamp_max);
            cached_decoder_ = std::make_unique<MWPMDecoder>(
                code, cached_weight_field_.get(), mwpm_weight_scale);
        }

        cached_code_ = &code;
        cached_weight_mode_ = weight_mode;
        cached_p_error_ = p_error;
        cached_seed_ = seed;
        cached_weight_scale_ = mwpm_weight_scale;
        cached_llr_p_data_ = llr_p_data;
        cached_llr_p_meas_ = llr_p_meas;
        cached_llr_p_idle_ = llr_p_idle;
        cached_llr_clamp_min_ = llr_clamp_min;
        cached_llr_clamp_max_ = llr_clamp_max;
    }

    return bitmaskToCorrection(cached_decoder_->decode(syn));
}
