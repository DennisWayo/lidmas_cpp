#pragma once

#include <vector>
#include "surface/MatchingProblem.h"
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

private:
    const SurfaceCode& code_;
};
