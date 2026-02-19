#pragma once

#include <vector>
#include "surface/ISurfaceDecoder.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfacePipeline.h"

class MWPMStubDecoder : public ISurfaceDecoder {
public:
    explicit MWPMStubDecoder(const SurfaceCode& code);

    std::vector<int> decode(const SurfaceSyndrome& syn) override;

private:
    const SurfaceCode& code_;
    SurfacePipeline pipeline_;
};
