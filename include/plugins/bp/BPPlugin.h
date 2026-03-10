#pragma once

#include <memory>
#include <string>

#include "core/DecoderConfig.h"
#include "decoders/BeliefPropagation.h"
#include "surface/ISurfaceDecoderPlugin.h"
#include "surface/SurfaceDecoder.h"

class BPPlugin : public ISurfaceDecoderPlugin {
public:
    std::string name() const override;
    std::string family() const override;
    void configure(const DecoderConfig& cfg) override;
    SurfaceCorrection decode(const SurfaceSyndrome& syn, const SurfaceCode& code) override;

private:
    DecoderConfig cfg_;
    const SurfaceCode* cached_code_ = nullptr;
    BeliefPropagation::Params cached_params_{};
    std::unique_ptr<SurfaceDecoder> cached_decoder_;
    std::string cached_mode_ = "sum-product";
};
