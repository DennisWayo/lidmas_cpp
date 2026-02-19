#include "surface/SurfacePipeline.h"

#include <stdexcept>

SurfacePipeline::SurfacePipeline(const SurfaceCode& code)
    : code_(code) {}

SyndromeGraph SurfacePipeline::buildSyndromeGraphFromSz(const std::vector<int>& sz) const {
    if (static_cast<int>(sz.size()) != code_.mz()) {
        throw std::invalid_argument("SurfacePipeline expected sz with length code.mz()");
    }

    const int d = code_.lattice().distance();
    const int width = d - 1;
    const int height = d - 1;
    SyndromeGraph g(width, height);

    for (int r = 0; r < static_cast<int>(sz.size()); ++r) {
        if ((sz[r] & 1) == 0) continue;
        const int x = r % width;
        const int y = r / width;
        g.addNode(x, y, 0);
    }
    return g;
}

SyndromeGraph SurfacePipeline::buildSyndromeGraphFromSx(const std::vector<int>& sx) const {
    if (static_cast<int>(sx.size()) != code_.mx()) {
        throw std::invalid_argument("SurfacePipeline expected sx with length code.mx()");
    }

    const int d = code_.lattice().distance();
    SyndromeGraph g(d, d);

    for (int r = 0; r < static_cast<int>(sx.size()); ++r) {
        if ((sx[r] & 1) == 0) continue;
        const int x = r % d;
        const int y = r / d;
        g.addNode(x, y, 0);
    }
    return g;
}

MatchingProblem SurfacePipeline::buildMatchingProblemFromSz(const std::vector<int>& sz) const {
    MatchingProblem mp;
    mp.buildFromSyndromeGraph(buildSyndromeGraphFromSz(sz));
    return mp;
}

MatchingProblem SurfacePipeline::buildMatchingProblemFromSyndrome(const SurfaceSyndrome& syn) const {
    MatchingProblem mp;
    if (!syn.sz.empty()) {
        mp.buildFromSyndromeGraph(buildSyndromeGraphFromSz(syn.sz));
    } else if (!syn.sx.empty()) {
        mp.buildFromSyndromeGraph(buildSyndromeGraphFromSx(syn.sx));
    }
    return mp;
}
