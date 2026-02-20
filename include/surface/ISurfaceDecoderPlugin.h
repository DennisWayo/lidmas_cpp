#pragma once

#include "core/IDecoderPlugin.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfaceCorrection.h"
#include "surface/SurfaceSyndrome.h"

class ISurfaceDecoderPlugin : public IDecoderPlugin {
public:
    using Correction = SurfaceCorrection;

    ~ISurfaceDecoderPlugin() override = default;
    virtual SurfaceCorrection decode(const SurfaceSyndrome& syn, const SurfaceCode& code) = 0;
};
