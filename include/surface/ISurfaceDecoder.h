#pragma once

#include <vector>
#include "surface/SurfaceSyndrome.h"

class ISurfaceDecoder {
public:
    virtual ~ISurfaceDecoder() = default;
    virtual std::vector<int> decode(const SurfaceSyndrome& syn) = 0;
};
