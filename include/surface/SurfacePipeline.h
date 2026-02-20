#pragma once

#include <vector>
#include "surface/MatchingProblem.h"
#include "surface/SurfaceCorrection.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfaceSyndrome.h"
#include "surface/SyndromeGraph.h"

class SurfacePipeline {
public:
    explicit SurfacePipeline(const SurfaceCode& code);

    SyndromeGraph buildSyndromeGraphFromSz(const std::vector<int>& sz) const;
    SyndromeGraph buildSyndromeGraphFromSx(const std::vector<int>& sx) const;

    MatchingProblem buildMatchingProblemFromSz(const std::vector<int>& sz) const;
    MatchingProblem buildMatchingProblemFromSyndrome(const SurfaceSyndrome& syn) const;
    static std::vector<int> correctionBitmask(const SurfaceCorrection& corr, int n_data);
    static int correctionWeight(const SurfaceCorrection& corr, int n_data);
    static std::vector<int> applyCorrection(const std::vector<int>& data_error,
                                            const SurfaceCorrection& corr,
                                            int n_data);

private:
    const SurfaceCode& code_;
};
