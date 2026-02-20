#include "plugins/neural/NeuralMWPMPlugin.h"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

#include "surface/BlossomMWPM.h"
#include "surface/MatchingProblem.h"
#include "surface/MWPMDecoder.h"
#include "surface/SurfacePipeline.h"

namespace {

int hIndex(int x, int y, int d) {
    if (x < 0 || x >= d - 1 || y < 0 || y >= d) {
        throw std::out_of_range("NeuralMWPMPlugin::hIndex out of range");
    }
    return y * (d - 1) + x;
}

int vIndex(int x, int y, int d) {
    if (x < 0 || x >= d || y < 0 || y >= d - 1) {
        throw std::out_of_range("NeuralMWPMPlugin::vIndex out of range");
    }
    const int h_count = d * (d - 1);
    return h_count + y * d + x;
}

void toggleH(int x, int y, int d, std::vector<int>& corr) {
    corr[hIndex(x, y, d)] ^= 1;
}

void toggleV(int x, int y, int d, std::vector<int>& corr) {
    corr[vIndex(x, y, d)] ^= 1;
}

bool syndromeMatches(const BinaryMatrix& H,
                     const std::vector<int>& corr,
                     const std::vector<int>& target) {
    if (target.empty()) return true;
    std::vector<int> syn = H.multiply(corr);
    if (syn.size() != target.size()) return false;
    for (size_t i = 0; i < syn.size(); ++i) {
        if ((syn[i] & 1) != (target[i] & 1)) return false;
    }
    return true;
}

std::vector<double> pairFeatures(const NeuralMWPMPlugin::Defect& a,
                                 const NeuralMWPMPlugin::Defect& b,
                                 bool plaquette_mode,
                                 int d_code) {
    const double dx = static_cast<double>(std::abs(a.x - b.x));
    const double dy = static_cast<double>(std::abs(a.y - b.y));
    const int max_coord = plaquette_mode ? (d_code - 2) : (d_code - 1);
    const bool near_a = (a.x == 0 || a.y == 0 || a.x == max_coord || a.y == max_coord);
    const bool near_b = (b.x == 0 || b.y == 0 || b.x == max_coord || b.y == max_coord);
    const double near_boundary = (near_a || near_b) ? 1.0 : 0.0;
    return {dx, dy, near_boundary};
}

std::vector<double> boundaryFeatures(const NeuralMWPMPlugin::Defect& a,
                                     bool plaquette_mode,
                                     int d_code) {
    (void)a;
    (void)plaquette_mode;
    (void)d_code;
    return {0.0, 0.0, 1.0};
}

int guidedWeight(const NeuralWeightModel& model,
                 int original_weight,
                 const std::vector<double>& features) {
    const double dx = features.size() > 0 ? features[0] : 0.0;
    const double dy = features.size() > 1 ? features[1] : 0.0;
    const double near_boundary = features.size() > 2 ? features[2] : 0.0;
    const double scale = model.predictScale(dx + dy, dx, dy, near_boundary);
    const double guided = std::max(0.0, static_cast<double>(original_weight) * scale);
    return static_cast<int>(std::llround(guided));
}

int baseBoundaryWeight(const NeuralMWPMPlugin::Defect& d,
                       int d_code,
                       bool plaquette_mode) {
    if (plaquette_mode) {
        const int f = d_code - 1;
        const int left = d.x + 1;
        const int right = f - d.x;
        const int bottom = d.y + 1;
        const int top = f - d.y;
        return std::min(std::min(left, right), std::min(bottom, top));
    }

    const int left = d.x;
    const int right = (d_code - 1) - d.x;
    const int bottom = d.y;
    const int top = (d_code - 1) - d.y;
    return std::min(std::min(left, right), std::min(bottom, top));
}

} // namespace

std::string NeuralMWPMPlugin::name() const {
    return "neural_mwpm";
}

std::string NeuralMWPMPlugin::family() const {
    return "surface";
}

void NeuralMWPMPlugin::configure(const DecoderConfig& cfg) {
    cfg_ = cfg;

    std::string new_path;
    const auto it = cfg.string_params.find("neural_model");
    if (it != cfg.string_params.end()) new_path = it->second;

    if (new_path != model_path_) {
        model_path_ = new_path;
        model_loaded_ = model_.loadFromJson(model_path_);
        status_reported_ = false;
    }

    if (!status_reported_) {
        if (model_loaded_) {
            std::cout << "Neural MWPM: model=ENABLED (" << model_path_ << ")\n";
        } else {
            std::cout << "Neural MWPM: model=DISABLED (no/invalid model file)\n";
        }
        status_reported_ = true;
    }
}

SurfaceCorrection NeuralMWPMPlugin::decode(const SurfaceSyndrome& syn, const SurfaceCode& code) {
    if (!model_loaded_) {
        MWPMDecoder base(code);
        return bitmaskToCorrection(base.decode(syn));
    }

    std::vector<int> corr(code.n(), 0);

    if (!syn.sz.empty()) {
        const std::vector<int> part = solveWithGuidance(code, syn.sz, true);
        for (int i = 0; i < code.n(); ++i) corr[i] ^= (part[i] & 1);
    }
    if (!syn.sx.empty()) {
        const std::vector<int> part = solveWithGuidance(code, syn.sx, false);
        for (int i = 0; i < code.n(); ++i) corr[i] ^= (part[i] & 1);
    }

    return bitmaskToCorrection(corr);
}

std::vector<int> NeuralMWPMPlugin::solveWithGuidance(const SurfaceCode& code,
                                                     const std::vector<int>& syndrome,
                                                     bool plaquette_mode) const {
    SurfacePipeline pipeline(code);
    MatchingProblem mp;
    if (plaquette_mode) {
        mp = pipeline.buildMatchingProblemFromSz(syndrome);
    } else {
        SyndromeGraph g = pipeline.buildSyndromeGraphFromSx(syndrome);
        mp.buildFromSyndromeGraph(g);
    }

    const int k = mp.numDefects();
    std::vector<int> corr(code.n(), 0);
    if (k == 0) return corr;

    std::vector<Defect> defects;
    defects.reserve(k);
    for (const auto& node : mp.defects()) {
        Defect d;
        d.id = node.id;
        d.x = node.x;
        d.y = node.y;
        defects.push_back(d);
    }

    std::vector<std::vector<int>> pair_weights(k, std::vector<int>(k, 0));
    std::vector<int> boundary_weights(k, 0);
    const int d_code = code.lattice().distance();
    for (int i = 0; i < k; ++i) {
        const int bw = baseBoundaryWeight(defects[i], d_code, plaquette_mode);
        boundary_weights[i] = guidedWeight(
            model_,
            bw,
            boundaryFeatures(defects[i], plaquette_mode, d_code));
        for (int j = i + 1; j < k; ++j) {
            const int w = mp.pairWeight(i, j);
            const int gw = guidedWeight(
                model_,
                w,
                pairFeatures(defects[i], defects[j], plaquette_mode, d_code));
            pair_weights[i][j] = gw;
            pair_weights[j][i] = gw;
        }
    }

    const std::vector<int> partner = solveMatchingWithBoundary(defects, pair_weights, boundary_weights);

    const int d = code.lattice().distance();
    const int f = d - 1;
    for (int i = 0; i < k; ++i) {
        const int j = partner[i];
        if (j < 0) continue;
        if (j >= k) {
            int x = defects[i].x;
            int y = defects[i].y;

            if (plaquette_mode) {
                const int left = x + 1;
                const int right = f - x;
                const int bottom = y + 1;
                const int top = f - y;
                switch (argmin4(left, right, bottom, top)) {
                    case 0:
                        while (x >= 0) {
                            toggleV(x, y, d, corr);
                            --x;
                        }
                        break;
                    case 1:
                        while (x < f) {
                            toggleV(x + 1, y, d, corr);
                            ++x;
                        }
                        break;
                    case 2:
                        while (y >= 0) {
                            toggleH(x, y, d, corr);
                            --y;
                        }
                        break;
                    default:
                        while (y < f) {
                            toggleH(x, y + 1, d, corr);
                            ++y;
                        }
                        break;
                }
            } else {
                const int left = x;
                const int right = (d - 1) - x;
                const int bottom = y;
                const int top = (d - 1) - y;
                switch (argmin4(left, right, bottom, top)) {
                    case 0:
                        while (x > 0) {
                            toggleH(x - 1, y, d, corr);
                            --x;
                        }
                        break;
                    case 1:
                        while (x < d - 1) {
                            toggleH(x, y, d, corr);
                            ++x;
                        }
                        break;
                    case 2:
                        while (y > 0) {
                            toggleV(x, y - 1, d, corr);
                            --y;
                        }
                        break;
                    default:
                        while (y < d - 1) {
                            toggleV(x, y, d, corr);
                            ++y;
                        }
                        break;
                }
            }
        } else if (i < j) {
            int x = defects[i].x;
            int y = defects[i].y;
            const int tx = defects[j].x;
            const int ty = defects[j].y;

            if (plaquette_mode) {
                while (x < tx) {
                    toggleV(x + 1, y, d, corr);
                    ++x;
                }
                while (x > tx) {
                    toggleV(x, y, d, corr);
                    --x;
                }
                while (y < ty) {
                    toggleH(x, y + 1, d, corr);
                    ++y;
                }
                while (y > ty) {
                    toggleH(x, y, d, corr);
                    --y;
                }
            } else {
                while (x < tx) {
                    toggleH(x, y, d, corr);
                    ++x;
                }
                while (x > tx) {
                    toggleH(x - 1, y, d, corr);
                    --x;
                }
                while (y < ty) {
                    toggleV(x, y, d, corr);
                    ++y;
                }
                while (y > ty) {
                    toggleV(x, y - 1, d, corr);
                    --y;
                }
            }
        }
    }

    const BinaryMatrix& H = plaquette_mode ? code.Hz() : code.Hx();
    if (!syndromeMatches(H, corr, syndrome)) {
        throw std::runtime_error("NeuralMWPMPlugin failed to reproduce target syndrome");
    }

    return corr;
}

std::vector<int> NeuralMWPMPlugin::solveMatchingWithBoundary(
    const std::vector<Defect>& defects,
    const std::vector<std::vector<int>>& pair_weights,
    const std::vector<int>& boundary_weights) const {
    const int k = static_cast<int>(defects.size());
    if (k == 0) return {};

    const int n = 2 * k;
    const int inf = std::numeric_limits<int>::max() / 8;
    std::vector<std::vector<int>> w(n, std::vector<int>(n, inf));
    for (int i = 0; i < n; ++i) w[i][i] = 0;

    for (int i = 0; i < k; ++i) {
        for (int j = i + 1; j < k; ++j) {
            const int wij = pair_weights[i][j];
            w[i][j] = wij;
            w[j][i] = wij;
        }
        const int bi = k + i;
        w[i][bi] = boundary_weights[i];
        w[bi][i] = boundary_weights[i];
    }

    for (int i = 0; i < k; ++i) {
        const int bi = k + i;
        for (int j = i + 1; j < k; ++j) {
            const int bj = k + j;
            w[bi][bj] = 0;
            w[bj][bi] = 0;
        }
    }

    return BlossomMWPM::solve(w);
}

int NeuralMWPMPlugin::argmin4(int a, int b, int c, int d) {
    int idx = 0;
    int best = a;
    if (b < best) {
        best = b;
        idx = 1;
    }
    if (c < best) {
        best = c;
        idx = 2;
    }
    if (d < best) {
        idx = 3;
    }
    return idx;
}

SurfaceCorrection NeuralMWPMPlugin::bitmaskToCorrection(const std::vector<int>& bitmask) {
    SurfaceCorrection corr;
    corr.qubit_flips.reserve(bitmask.size());
    for (int i = 0; i < static_cast<int>(bitmask.size()); ++i) {
        if ((bitmask[i] & 1) != 0) corr.qubit_flips.push_back(i);
    }
    corr.weight = static_cast<int>(corr.qubit_flips.size());
    return corr;
}
