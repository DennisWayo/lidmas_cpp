#pragma once

#include <memory>
#include <string>

#include "WeightField.h"
#include "core/DecoderConfig.h"
#include "decoders/UnionFindDecoder.h"
#include "surface/ISurfaceDecoderPlugin.h"
#include "surface/UnionFindDecoder.h"

class UnionFindPlugin : public ISurfaceDecoderPlugin {
public:
    std::string name() const override;
    std::string family() const override;
    void configure(const DecoderConfig& cfg) override;
    SurfaceCorrection decode(const SurfaceSyndrome& syn, const SurfaceCode& code) override;

private:
    DecoderConfig cfg_;
    const SurfaceCode* cached_code_ = nullptr;
    bool cached_weighted_mode_ = false;
    std::string cached_neural_weights_path_;
    std::string cached_weight_mode_ = "uniform";
    uint64_t cached_seed_ = 0;
    double cached_p_error_ = -1.0;
    std::unique_ptr<WeightField> cached_weight_field_;
    std::unique_ptr<UnionFindDecoder> cached_decoder_;
    std::unique_ptr<lidmas_v07::UnionFindDecoder> cached_weighted_decoder_;
};
