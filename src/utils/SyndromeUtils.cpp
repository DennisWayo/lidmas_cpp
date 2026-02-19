#include "utils/SyndromeUtils.h"

bool parity_satisfied(const BinaryMatrix& H, const std::vector<int>& x) {
    const std::vector<int> s = H.multiply(x);
    for (int v : s) {
        if ((v & 1) != 0) return false;
    }
    return true;
}

std::vector<int> zero_syndrome(int m) {
    return std::vector<int>(m, 0);
}
