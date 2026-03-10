#include "plugins/bp/BPPlugin.h"

#include <algorithm>
#include <string>

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

BeliefPropagation::Mode parseMode(const std::string& mode) {
    if (mode == "nms" || mode == "bp_nms" || mode == "normalized_min_sum") {
        return BeliefPropagation::Mode::NORMALIZED_MIN_SUM;
    }
    if (mode == "sum-product" || mode == "sum_product" || mode == "sp") {
        return BeliefPropagation::Mode::SUM_PRODUCT;
    }
    return BeliefPropagation::Mode::SUM_PRODUCT;
}

} // namespace

std::string BPPlugin::name() const {
    return "bp";
}

std::string BPPlugin::family() const {
    return "surface";
}

void BPPlugin::configure(const DecoderConfig& cfg) {
    cfg_ = cfg;
}

SurfaceCorrection BPPlugin::decode(const SurfaceSyndrome& syn, const SurfaceCode& code) {
    const std::string mode_name = [&]() {
        const auto it = cfg_.string_params.find("bp_mode");
        return (it == cfg_.string_params.end()) ? std::string("sum-product") : it->second;
    }();

    BeliefPropagation::Params params;
    params.max_iters = cfg_.max_iters;
    params.alpha = cfg_.alpha;
    params.damping = cfg_.damping;
    params.llr_max = cfg_.llr_max;
    params.mode = parseMode(mode_name);
    params.convergence_tol = 1e-6;

    const bool rebuild = (cached_decoder_ == nullptr)
        || (cached_code_ != &code)
        || (cached_mode_ != mode_name)
        || (cached_params_.max_iters != params.max_iters)
        || (cached_params_.alpha != params.alpha)
        || (cached_params_.damping != params.damping)
        || (cached_params_.llr_max != params.llr_max);

    if (rebuild) {
        cached_decoder_ = std::make_unique<SurfaceDecoder>(params);
        cached_code_ = &code;
        cached_params_ = params;
        cached_mode_ = mode_name;
    }

    SurfaceSyndrome full;
    full.ex.assign(code.n(), 0);
    full.ez.assign(code.n(), 0);
    full.sx = syn.sx;
    full.sz = syn.sz;
    if (full.sx.empty()) full.sx.assign(code.mx(), 0);
    if (full.sz.empty()) full.sz.assign(code.mz(), 0);

    const double p_error = cfg_.p;
    const auto decoded = cached_decoder_->decode(code, full, p_error, p_error);
    return bitmaskToCorrection(decoded.cx);
}
