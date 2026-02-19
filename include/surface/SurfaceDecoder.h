#pragma once

#include <vector>
#include "decoders/BeliefPropagation.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfaceSyndrome.h"

class SurfaceDecoder {
public:
    struct DecodeResult {
        std::vector<int> cx;
        std::vector<int> cz;
        bool logicalXFail = false;
        bool logicalZFail = false;
        bool logicalFail = false;
        int itersX = 0;
        int itersZ = 0;
        bool max_iter_hit_X = false;
        bool max_iter_hit_Z = false;
    };

    explicit SurfaceDecoder(BeliefPropagation::Params params = {});

    DecodeResult decode(const SurfaceCode& code,
                        const SurfaceSyndrome& s,
                        double px,
                        double pz) const;

private:
    BeliefPropagation::Params params_;
};
