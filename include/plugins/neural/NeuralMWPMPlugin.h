#pragma once

#include <string>
#include <vector>
#include "core/DecoderConfig.h"
#include "plugins/neural/NeuralWeightModel.h"
#include "surface/ISurfaceDecoderPlugin.h"

class NeuralMWPMPlugin : public ISurfaceDecoderPlugin {
public:
    struct Defect {
        int id = -1;
        int x = 0;
        int y = 0;
    };

    std::string name() const override;
    std::string family() const override;
    void configure(const DecoderConfig& cfg) override;
    SurfaceCorrection decode(const SurfaceSyndrome& syn, const SurfaceCode& code) override;

private:
    DecoderConfig cfg_;
    NeuralWeightModel model_;
    std::string model_path_;
    bool model_loaded_ = false;
    bool status_reported_ = false;

    std::vector<int> solveWithGuidance(const SurfaceCode& code,
                                       const std::vector<int>& syndrome,
                                       bool plaquette_mode) const;
    std::vector<int> solveMatchingWithBoundary(const std::vector<Defect>& defects,
                                               const std::vector<std::vector<int>>& pair_weights,
                                               const std::vector<int>& boundary_weights) const;
    static int argmin4(int a, int b, int c, int d);

    static SurfaceCorrection bitmaskToCorrection(const std::vector<int>& bitmask);
};
