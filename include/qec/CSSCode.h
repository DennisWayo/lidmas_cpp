#pragma once

#include <vector>
#include "core/BinaryMatrix.h"

class CSSCode {
public:
    CSSCode(BinaryMatrix Hx, BinaryMatrix Hz);

    const BinaryMatrix& Hx() const { return hx_; }
    const BinaryMatrix& Hz() const { return hz_; }

    int n() const { return hx_.cols(); }
    int mx() const { return hx_.rows(); }
    int mz() const { return hz_.rows(); }

    bool validateCSS() const;

    void setLogicalX(std::vector<std::vector<int>> Lx);
    void setLogicalZ(std::vector<std::vector<int>> Lz);

    const std::vector<std::vector<int>>& logicalX() const { return lx_; }
    const std::vector<std::vector<int>>& logicalZ() const { return lz_; }

    bool hasLogicals() const;

private:
    BinaryMatrix hx_;
    BinaryMatrix hz_;
    std::vector<std::vector<int>> lx_;
    std::vector<std::vector<int>> lz_;
};
