#include "qec/CSSSyndrome.h"

std::vector<int> computeSyndrome(const BinaryMatrix& H,
                                 const std::vector<int>& e) {
    std::vector<int> s = H.multiply(e);
    for (int& v : s) v &= 1;
    return s;
}
