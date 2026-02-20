#pragma once

#include <vector>
#include "surface/SurfaceSyndrome.h"

class ISurfaceDecoder {
public:
    using Recovery = std::vector<int>;  // data-qubit flip bitmask (length n_data, values 0/1)

    virtual ~ISurfaceDecoder() = default;
    virtual Recovery decode(const SurfaceSyndrome& syn) = 0;
};
