#pragma once

#include <vector>
#include "core/BinaryMatrix.h"

struct CSSSyndrome {
    std::vector<int> sx;  // syndrome from Hx (detect Z errors)
    std::vector<int> sz;  // syndrome from Hz (detect X errors)
};

std::vector<int> computeSyndrome(const BinaryMatrix& H,
                                 const std::vector<int>& e);
