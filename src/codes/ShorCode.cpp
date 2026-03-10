#include "codes/ShorCode.h"

#include <stdexcept>

void ShorCode::buildCSS(BinaryMatrix* hx, BinaryMatrix* hz, LogicalOperators* logicals) {
    if (hx == nullptr || hz == nullptr || logicals == nullptr) {
        throw std::invalid_argument("ShorCode::buildCSS requires non-null outputs");
    }

    BinaryMatrix Hx(2, 9);
    for (int i = 0; i < 6; ++i) Hx.set(0, i, 1);
    for (int i = 3; i < 9; ++i) Hx.set(1, i, 1);

    BinaryMatrix Hz(6, 9);
    Hz.set(0, 0, 1); Hz.set(0, 1, 1);
    Hz.set(1, 1, 1); Hz.set(1, 2, 1);
    Hz.set(2, 3, 1); Hz.set(2, 4, 1);
    Hz.set(3, 4, 1); Hz.set(3, 5, 1);
    Hz.set(4, 6, 1); Hz.set(4, 7, 1);
    Hz.set(5, 7, 1); Hz.set(5, 8, 1);

    LogicalOperators ops;
    ops.LX = {{1, 1, 1, 1, 1, 1, 1, 1, 1}};
    ops.LZ = {{1, 0, 0, 1, 0, 0, 1, 0, 0}};

    *hx = std::move(Hx);
    *hz = std::move(Hz);
    *logicals = std::move(ops);
}
