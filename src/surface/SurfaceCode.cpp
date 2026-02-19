#include "surface/SurfaceCode.h"

BinaryMatrix SurfaceCode::buildCheckMatrix_(
    int n_cols,
    const std::vector<std::vector<int>>& supports) {
    BinaryMatrix H(static_cast<int>(supports.size()), n_cols);
    for (int r = 0; r < (int)supports.size(); ++r) {
        for (int q : supports[r]) {
            H.set(r, q, 1);
        }
    }
    return H;
}

SurfaceCode::SurfaceCode(int d)
    : lattice_(d),
      hx_(buildCheckMatrix_(lattice_.numDataQubits(), lattice_.xCheckSupports())),
      hz_(buildCheckMatrix_(lattice_.numDataQubits(), lattice_.zCheckSupports())) {}
