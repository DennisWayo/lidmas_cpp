#pragma once

#include "core/DecoderConfig.h"
#include "surface/ISurfaceDecoderPlugin.h"

class StubSurfacePlugin : public ISurfaceDecoderPlugin {
public:
    std::string name() const override;
    std::string family() const override;
    void configure(const DecoderConfig& cfg) override;
    SurfaceCorrection decode(const SurfaceSyndrome& syn, const SurfaceCode& code) override;

private:
    DecoderConfig cfg_;
};
