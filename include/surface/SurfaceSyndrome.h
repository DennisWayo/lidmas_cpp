#pragma once

#include <cstdint>
#include <vector>
#include "surface/SurfaceCode.h"

struct SurfaceSyndrome {
    std::vector<int> ex;
    std::vector<int> ez;
    std::vector<int> sx;
    std::vector<int> sz;

    static SurfaceSyndrome sample(const SurfaceCode& code,
                                  double px,
                                  double pz,
                                  uint64_t seed);
};
