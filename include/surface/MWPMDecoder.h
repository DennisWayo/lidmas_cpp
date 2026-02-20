#pragma once

#include <string>
#include <vector>
#include "WeightField.h"
#include "UniformWeightField.h"
#include "core/BinaryMatrix.h"
#include "surface/BlossomMWPM.h"
#include "surface/ISurfaceDecoder.h"
#include "surface/SurfaceCode.h"
#include "surface/SyndromeGraph.h"

class MWPMDecoder : public ISurfaceDecoder {
public:
    enum class GraphMode {
        FULL = 0,
        SIMPLE = 1
    };

    enum class BoundarySide {
        LEFT = 0,
        RIGHT = 1,
        BOTTOM = 2,
        TOP = 3
    };

    struct Defect {
        int id = -1;
        LatticeCoord rc;
        bool boundary_flag = false;
    };

    explicit MWPMDecoder(const SurfaceCode& code);
    MWPMDecoder(const SurfaceCode& code, GraphMode graph_mode);
    MWPMDecoder(const SurfaceCode& code, const WeightField* weight_field, double weight_scale = 1000.0);
    MWPMDecoder(const SurfaceCode& code,
                const WeightField* weight_field,
                double weight_scale,
                GraphMode graph_mode);
    std::vector<int> decode(const SurfaceSyndrome& syn) override;

    static GraphMode parseGraphMode(const std::string& graph_mode);
    static const char* graphModeName(GraphMode mode);

private:
    const SurfaceCode& code_;
    int d_ = 0;
    UniformWeightField uniform_weight_field_;
    const WeightField* weight_field_ = nullptr;
    bool weighted_mode_ = false;
    double weight_scale_ = 1000.0;
    GraphMode graph_mode_ = GraphMode::FULL;

    int hIndex(int x, int y) const;
    int vIndex(int x, int y) const;
    void toggleH(int x, int y, std::vector<int>& corr) const;
    void toggleV(int x, int y, std::vector<int>& corr) const;

    std::vector<Defect> defectsFromPlaquetteSyndrome(const std::vector<int>& sz) const;
    std::vector<Defect> defectsFromStarSyndrome(const std::vector<int>& sx) const;
    int manhattan(const Defect& a, const Defect& b) const;
    int weightedCost(const Defect& a, const Defect& b, bool plaquette_mode) const;
    int weightedBoundaryCost(const Defect& d, bool plaquette_mode) const;
    int DistToBoundaryZ(LatticeCoord zdef, int d) const;
    int DistToBoundaryX(LatticeCoord xdef, int d) const;
    int boundaryDistance(const Defect& d, bool plaquette_mode) const;
    std::vector<int> solveMatchingSimple(const std::vector<Defect>& defects,
                                         bool plaquette_mode) const;
    std::vector<int> solveMatchingWithBoundary(const std::vector<Defect>& defects,
                                               bool plaquette_mode) const;

    std::vector<LatticeCoord> PathBetweenDefectsZ(LatticeCoord a, LatticeCoord b, int d) const;
    std::vector<LatticeCoord> PathToBoundaryZ(LatticeCoord a, int d, BoundarySide* chosen_side) const;
    std::vector<LatticeCoord> PathBetweenDefectsX(LatticeCoord a, LatticeCoord b, int d) const;
    std::vector<LatticeCoord> PathToBoundaryX(LatticeCoord a, int d, BoundarySide* chosen_side) const;

    void applyPlaquettePairPath(const Defect& a, const Defect& b, std::vector<int>& corr) const;
    void applyStarPairPath(const Defect& a, const Defect& b, std::vector<int>& corr) const;
    void applyPlaquetteBoundaryPath(const Defect& d, std::vector<int>& corr, BoundarySide* chosen_side) const;
    void applyStarBoundaryPath(const Defect& d, std::vector<int>& corr, BoundarySide* chosen_side) const;

    bool syndromeMatches(const BinaryMatrix& H,
                         const std::vector<int>& corr,
                         const std::vector<int>& target) const;
};
