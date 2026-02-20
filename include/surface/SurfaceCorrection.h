#pragma once

#include <vector>

struct SurfaceCorrection {
    std::vector<int> qubit_flips;
    int weight = 0;
};
