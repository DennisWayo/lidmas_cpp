#pragma once

#include <vector>
#include "core/BinaryMatrix.h"

bool parity_satisfied(const BinaryMatrix& H, const std::vector<int>& x);
std::vector<int> zero_syndrome(int m);
