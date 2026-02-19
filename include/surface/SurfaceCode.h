#pragma once

#include "core/BinaryMatrix.h"
#include "surface/SurfaceLattice.h"

class SurfaceCode {
public:
    explicit SurfaceCode(int d);

    const BinaryMatrix& Hx() const { return hx_; }
    const BinaryMatrix& Hz() const { return hz_; }

    int n() const { return lattice_.numDataQubits(); }
    int mx() const { return lattice_.numXChecks(); }
    int mz() const { return lattice_.numZChecks(); }

    const SurfaceLattice& lattice() const { return lattice_; }
    const std::vector<int>& logicalXSupport() const { return lattice_.logicalXSupport(); }
    const std::vector<int>& logicalZSupport() const { return lattice_.logicalZSupport(); }

private:
    SurfaceLattice lattice_;
    BinaryMatrix hx_;
    BinaryMatrix hz_;

    static BinaryMatrix buildCheckMatrix_(
        int n_cols,
        const std::vector<std::vector<int>>& supports);
};
