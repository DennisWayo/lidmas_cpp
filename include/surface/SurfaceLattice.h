#pragma once

#include <vector>

// Planar surface-code lattice with data qubits on edges of a d x d vertex grid.
class SurfaceLattice {
public:
    explicit SurfaceLattice(int d);

    int distance() const { return d_; }
    int numDataQubits() const { return n_data_; }
    int numXChecks() const { return n_x_checks_; }
    int numZChecks() const { return n_z_checks_; }

    const std::vector<std::vector<int>>& xCheckSupports() const { return x_supports_; }
    const std::vector<std::vector<int>>& zCheckSupports() const { return z_supports_; }

    // Canonical logical supports (bitmasks of length numDataQubits()).
    const std::vector<int>& logicalXSupport() const { return logical_x_support_; }
    const std::vector<int>& logicalZSupport() const { return logical_z_support_; }

private:
    int d_ = 0;
    int n_data_ = 0;
    int n_x_checks_ = 0;
    int n_z_checks_ = 0;

    std::vector<std::vector<int>> x_supports_;
    std::vector<std::vector<int>> z_supports_;
    std::vector<int> logical_x_support_;
    std::vector<int> logical_z_support_;

    int hIndex_(int x, int y) const;
    int vIndex_(int x, int y) const;
    void buildCheckSupports_();
    void buildLogicalSupports_();
};
