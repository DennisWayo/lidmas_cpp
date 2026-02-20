#include "plugins/uf/UnionFindPlugin.h"

#include <memory>
#include <string>

#include "NeuralWeightField.h"
#include "UniformWeightField.h"
#include "decoders/UnionFindDecoder.h"
#include "surface/UnionFindDecoder.h"

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

std::string UnionFindPlugin::name() const {
    return "uf";
}

std::string UnionFindPlugin::family() const {
    return "surface";
}

void UnionFindPlugin::configure(const DecoderConfig& cfg) {
    cfg_ = cfg;
}

SurfaceCorrection UnionFindPlugin::decode(const SurfaceSyndrome& syn, const SurfaceCode& code) {
    std::string weight_mode = "uniform";
    auto weight_mode_it = cfg_.string_params.find("weight_mode");
    if (weight_mode_it != cfg_.string_params.end() && !weight_mode_it->second.empty()) {
        weight_mode = weight_mode_it->second;
    }
    if (weight_mode != "uniform" && weight_mode != "neural") {
        weight_mode = "uniform";
    }

    bool uf_weighted = false;
    auto weighted_it = cfg_.int_params.find("uf_weighted");
    if (weighted_it != cfg_.int_params.end()) {
        uf_weighted = (weighted_it->second != 0);
    }
    if (weight_mode == "neural") uf_weighted = true;

    std::string neural_weights_path;
    auto neural_it = cfg_.string_params.find("neural_weights");
    if (neural_it != cfg_.string_params.end()) {
        neural_weights_path = neural_it->second;
    }
    if (neural_weights_path.empty()) {
        auto fallback_it = cfg_.string_params.find("neural_model");
        if (fallback_it != cfg_.string_params.end()) {
            neural_weights_path = fallback_it->second;
        }
    }

    const double p_error = cfg_.p;
    const uint64_t seed = cfg_.seed;

    if (!uf_weighted) {
        if (cached_decoder_ == nullptr
            || cached_code_ != &code
            || cached_weighted_mode_
            || cached_weight_mode_ != "uniform") {
            cached_decoder_ = std::make_unique<UnionFindDecoder>(code);
            cached_weighted_decoder_.reset();
            cached_weight_field_.reset();
            cached_code_ = &code;
            cached_weighted_mode_ = false;
            cached_neural_weights_path_.clear();
            cached_weight_mode_ = "uniform";
            cached_p_error_ = -1.0;
            cached_seed_ = 0;
        }
        return bitmaskToCorrection(cached_decoder_->decode(syn));
    }

    const bool rebuild_weighted =
        (cached_weighted_decoder_ == nullptr
        || cached_code_ != &code
        || !cached_weighted_mode_
        || cached_weight_mode_ != weight_mode
        || cached_neural_weights_path_ != neural_weights_path);
    if (rebuild_weighted
        || (weight_mode == "neural" && (cached_p_error_ != p_error || cached_seed_ != seed))) {
        if (weight_mode == "neural") {
            cached_weight_field_ = std::make_unique<NeuralWeightField>(
                code.lattice().distance(), p_error, seed);
        } else {
            cached_weight_field_ = std::make_unique<UniformWeightField>();
        }

        lidmas_v07::UnionFindDecoder::Options opts;
        opts.uf_weighted = true;
        opts.p_error = p_error;
        cached_weighted_decoder_ = std::make_unique<lidmas_v07::UnionFindDecoder>(
            code, opts, cached_weight_field_.get());
        cached_decoder_.reset();
        cached_code_ = &code;
        cached_weighted_mode_ = true;
        cached_neural_weights_path_ = neural_weights_path;
        cached_weight_mode_ = weight_mode;
        cached_p_error_ = p_error;
        cached_seed_ = seed;
    }

    cached_weighted_decoder_->setWeighted(true);
    cached_weighted_decoder_->setChannelErrorRate(p_error);

    return bitmaskToCorrection(cached_weighted_decoder_->decodeSurface(syn));
}
