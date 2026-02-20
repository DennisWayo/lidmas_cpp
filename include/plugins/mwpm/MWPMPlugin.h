#pragma once

#include <memory>
#include <string>

#include "WeightField.h"
#include "core/DecoderConfig.h"
#include "surface/ISurfaceDecoderPlugin.h"
#include "surface/MWPMDecoder.h"

class MWPMPlugin : public ISurfaceDecoderPlugin {
public:
    std::string name() const override;
    std::string family() const override;
    void configure(const DecoderConfig& cfg) override;
    SurfaceCorrection decode(const SurfaceSyndrome& syn, const SurfaceCode& code) override;

private:
    DecoderConfig cfg_;
    const SurfaceCode* cached_code_ = nullptr;
    std::string cached_weight_mode_ = "uniform";
    uint64_t cached_seed_ = 0;
    double cached_p_error_ = -1.0;
    double cached_weight_scale_ = 1000.0;
    double cached_llr_p_data_ = -1.0;
    double cached_llr_p_meas_ = -1.0;
    double cached_llr_p_idle_ = -1.0;
    double cached_llr_clamp_min_ = 1e-12;
    double cached_llr_clamp_max_ = 1.0 - 1e-12;
    std::unique_ptr<WeightField> cached_weight_field_;
    std::unique_ptr<MWPMDecoder> cached_decoder_;
};
