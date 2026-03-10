#include "codes/RepetitionCode.h"

#include <stdexcept>

BinaryMatrix RepetitionCode::buildParityCheck(int n) {
    if (n < 2) {
        throw std::invalid_argument("RepetitionCode requires n >= 2");
    }
    BinaryMatrix H(n - 1, n);
    for (int i = 0; i < n - 1; ++i) {
        H.set(i, i, 1);
        H.set(i, i + 1, 1);
    }
    return H;
}

LogicalOperators RepetitionCode::buildLogicals(int n) {
    if (n < 2) {
        throw std::invalid_argument("RepetitionCode requires n >= 2");
    }
    LogicalOperators ops;
    std::vector<int> lx(n, 1);
    std::vector<int> lz(n, 0);
    lz[0] = 1;
    ops.LX = {lx};
    ops.LZ = {lz};
    return ops;
}

void RepetitionCode::buildCSS(int n, BinaryMatrix* hx, BinaryMatrix* hz, LogicalOperators* logicals) {
    if (hx == nullptr || hz == nullptr || logicals == nullptr) {
        throw std::invalid_argument("RepetitionCode::buildCSS requires non-null outputs");
    }
    if (n < 2) {
        throw std::invalid_argument("RepetitionCode requires n >= 2");
    }

    *hx = BinaryMatrix(0, n);
    *hz = buildParityCheck(n);
    *logicals = buildLogicals(n);
}
