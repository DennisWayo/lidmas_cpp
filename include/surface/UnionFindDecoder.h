#pragma once

#include <vector>
#include "core/BinaryMatrix.h"
#include "surface/ISurfaceDecoder.h"
#include "surface/SurfaceCode.h"

class UnionFindDecoder : public ISurfaceDecoder {
public:
    explicit UnionFindDecoder(const SurfaceCode& code);
    std::vector<int> decode(const SurfaceSyndrome& syn) override;

private:
    struct Defect {
        int id = -1;
        int x = 0;
        int y = 0;
        int vertex = -1;
        bool boundary_flag = false;
    };

    const SurfaceCode& code_;
    int d_ = 0;

    int hIndex(int x, int y) const;
    int vIndex(int x, int y) const;
    void toggleH(int x, int y, std::vector<int>& corr) const;
    void toggleV(int x, int y, std::vector<int>& corr) const;

    std::vector<int> decodeSyndromeUF(const std::vector<int>& syndrome, bool plaquette_mode) const;

    bool syndromeMatches(const BinaryMatrix& H,
                         const std::vector<int>& corr,
                         const std::vector<int>& target) const;
};
