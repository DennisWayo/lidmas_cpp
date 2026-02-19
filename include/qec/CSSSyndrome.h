#pragma once

#include <vector>

struct CSSSyndrome {
    std::vector<int> sx;  // syndrome from Hx (detect Z errors)
    std::vector<int> sz;  // syndrome from Hz (detect X errors)
};
