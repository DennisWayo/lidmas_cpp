#pragma once

#include <vector>
#include "core/BinaryMatrix.h"
#include "surface/BlossomMWPM.h"
#include "surface/ISurfaceDecoder.h"
#include "surface/SurfaceCode.h"

class MWPMDecoder : public ISurfaceDecoder {
public:
    struct Defect {
        int id = -1;
        int x = 0;
        int y = 0;
        bool boundary_flag = false;
    };

    explicit MWPMDecoder(const SurfaceCode& code);
    std::vector<int> decode(const SurfaceSyndrome& syn) override;

private:
    const SurfaceCode& code_;
    int d_ = 0;

    int hIndex(int x, int y) const;
    int vIndex(int x, int y) const;
    void toggleH(int x, int y, std::vector<int>& corr) const;
    void toggleV(int x, int y, std::vector<int>& corr) const;

    std::vector<Defect> defectsFromPlaquetteSyndrome(const std::vector<int>& sz) const;
    std::vector<Defect> defectsFromStarSyndrome(const std::vector<int>& sx) const;
    int manhattan(const Defect& a, const Defect& b) const;
    int boundaryDistance(const Defect& d, bool plaquette_mode) const;
    std::vector<int> solveMatchingWithBoundary(const std::vector<Defect>& defects,
                                               bool plaquette_mode) const;

    void applyPlaquettePairPath(const Defect& a, const Defect& b, std::vector<int>& corr) const;
    void applyStarPairPath(const Defect& a, const Defect& b, std::vector<int>& corr) const;
    void applyPlaquetteBoundaryPath(const Defect& d, std::vector<int>& corr) const;
    void applyStarBoundaryPath(const Defect& d, std::vector<int>& corr) const;

    bool syndromeMatches(const BinaryMatrix& H,
                         const std::vector<int>& corr,
                         const std::vector<int>& target) const;
};
