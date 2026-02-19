#include "surface/SurfaceLattice.h"
#include <stdexcept>

SurfaceLattice::SurfaceLattice(int d)
    : d_(d),
      n_data_(2 * d * (d - 1)),
      n_x_checks_(d * d),
      n_z_checks_((d - 1) * (d - 1)) {
    if (d < 3 || (d % 2) == 0) {
        throw std::invalid_argument("SurfaceLattice requires odd d >= 3");
    }
    buildCheckSupports_();
    buildLogicalSupports_();
}

int SurfaceLattice::hIndex_(int x, int y) const {
    if (x < 0 || x >= d_ - 1 || y < 0 || y >= d_) {
        throw std::out_of_range("hIndex out of range");
    }
    return y * (d_ - 1) + x;
}

int SurfaceLattice::vIndex_(int x, int y) const {
    if (x < 0 || x >= d_ || y < 0 || y >= d_ - 1) {
        throw std::out_of_range("vIndex out of range");
    }
    const int h_count = d_ * (d_ - 1);
    return h_count + y * d_ + x;
}

void SurfaceLattice::buildCheckSupports_() {
    x_supports_.clear();
    x_supports_.reserve(n_x_checks_);

    // X checks ("stars") on vertices.
    for (int y = 0; y < d_; ++y) {
        for (int x = 0; x < d_; ++x) {
            std::vector<int> support;
            support.reserve(4);

            if (x > 0) support.push_back(hIndex_(x - 1, y));
            if (x < d_ - 1) support.push_back(hIndex_(x, y));
            if (y > 0) support.push_back(vIndex_(x, y - 1));
            if (y < d_ - 1) support.push_back(vIndex_(x, y));

            x_supports_.push_back(support);
        }
    }

    z_supports_.clear();
    z_supports_.reserve(n_z_checks_);

    // Z checks ("plaquettes") on faces.
    for (int y = 0; y < d_ - 1; ++y) {
        for (int x = 0; x < d_ - 1; ++x) {
            std::vector<int> support;
            support.reserve(4);
            support.push_back(hIndex_(x, y));       // bottom
            support.push_back(hIndex_(x, y + 1));   // top
            support.push_back(vIndex_(x, y));       // left
            support.push_back(vIndex_(x + 1, y));   // right
            z_supports_.push_back(support);
        }
    }
}

void SurfaceLattice::buildLogicalSupports_() {
    logical_x_support_.assign(n_data_, 0);
    logical_z_support_.assign(n_data_, 0);

    const int mid = d_ / 2;

    // Canonical Z logical: primal vertical chain connecting top/bottom boundaries.
    for (int y = 0; y < d_ - 1; ++y) {
        logical_z_support_[vIndex_(mid, y)] = 1;
    }

    // Canonical X logical: dual horizontal path crossing vertical edges left/right.
    for (int x = 0; x < d_; ++x) {
        logical_x_support_[vIndex_(x, mid)] = 1;
    }
}
