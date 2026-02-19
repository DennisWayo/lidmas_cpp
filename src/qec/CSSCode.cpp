#include "qec/CSSCode.h"
#include <utility>

CSSCode::CSSCode(BinaryMatrix Hx, BinaryMatrix Hz)
    : hx_(std::move(Hx)),
      hz_(std::move(Hz)) {}

bool CSSCode::validateCSS() const {
    if (hx_.cols() != hz_.cols())
        return false;

    const int n = hx_.cols();
    for (int i = 0; i < hx_.rows(); ++i) {
        for (int j = 0; j < hz_.rows(); ++j) {
            int parity = 0;
            for (int k = 0; k < n; ++k) {
                parity ^= ((hx_.get(i, k) & 1) & (hz_.get(j, k) & 1));
            }
            if ((parity & 1) != 0)
                return false;
        }
    }
    return true;
}

void CSSCode::setLogicalX(std::vector<std::vector<int>> Lx) {
    lx_ = std::move(Lx);
}

void CSSCode::setLogicalZ(std::vector<std::vector<int>> Lz) {
    lz_ = std::move(Lz);
}

bool CSSCode::hasLogicals() const {
    return !lx_.empty() || !lz_.empty();
}
