#include "surface/MWPMDecoder.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

namespace {

MWPMDecoder::BoundarySide argmin4(int left, int right, int bottom, int top) {
    MWPMDecoder::BoundarySide side = MWPMDecoder::BoundarySide::LEFT;
    int best = left;
    if (right < best) {
        best = right;
        side = MWPMDecoder::BoundarySide::RIGHT;
    }
    if (bottom < best) {
        best = bottom;
        side = MWPMDecoder::BoundarySide::BOTTOM;
    }
    if (top < best) {
        side = MWPMDecoder::BoundarySide::TOP;
    }
    return side;
}

const char* sideName(MWPMDecoder::BoundarySide side) {
    switch (side) {
        case MWPMDecoder::BoundarySide::LEFT: return "LEFT";
        case MWPMDecoder::BoundarySide::RIGHT: return "RIGHT";
        case MWPMDecoder::BoundarySide::BOTTOM: return "BOTTOM";
        case MWPMDecoder::BoundarySide::TOP: return "TOP";
        default: return "UNKNOWN";
    }
}

std::string coordString(const LatticeCoord& rc) {
    std::ostringstream oss;
    oss << "(" << rc.r << "," << rc.c << ")";
    return oss.str();
}

std::string defectsString(const std::vector<MWPMDecoder::Defect>& defects) {
    std::ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < defects.size(); ++i) {
        if (i > 0) oss << ",";
        oss << coordString(defects[i].rc);
    }
    oss << "]";
    return oss.str();
}

std::string pairsString(const std::vector<std::pair<int, int>>& pairs,
                        const std::vector<MWPMDecoder::Defect>& defects) {
    std::ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < pairs.size(); ++i) {
        if (i > 0) oss << ",";
        oss << coordString(defects[pairs[i].first].rc)
            << "<->"
            << coordString(defects[pairs[i].second].rc);
    }
    oss << "]";
    return oss.str();
}

std::string boundaryString(
    const std::vector<std::pair<int, MWPMDecoder::BoundarySide>>& boundary_matches,
    const std::vector<MWPMDecoder::Defect>& defects) {
    std::ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < boundary_matches.size(); ++i) {
        if (i > 0) oss << ",";
        const int id = boundary_matches[i].first;
        oss << coordString(defects[id].rc) << "->" << sideName(boundary_matches[i].second);
    }
    oss << "]";
    return oss.str();
}

std::string syndromeString(const std::vector<int>& s) {
    std::ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < s.size(); ++i) {
        if (i > 0) oss << ",";
        oss << (s[i] & 1);
    }
    oss << "]";
    return oss.str();
}

std::string matchingPairsRawString(const std::vector<int>& partner, int k) {
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (int i = 0; i < k; ++i) {
        if (partner[i] < 0) continue;
        if (i > partner[i]) continue;
        if (!first) oss << ",";
        first = false;
        oss << "(" << i << "<->" << partner[i] << ")";
    }
    oss << "]";
    return oss.str();
}

} // namespace

MWPMDecoder::MWPMDecoder(const SurfaceCode& code)
    : code_(code),
      d_(code.lattice().distance()),
      weight_field_(&uniform_weight_field_),
      weighted_mode_(false),
      weight_scale_(1000.0) {}

MWPMDecoder::MWPMDecoder(const SurfaceCode& code,
                         const WeightField* weight_field,
                         double weight_scale)
    : code_(code),
      d_(code.lattice().distance()),
      weight_field_(weight_field ? weight_field : &uniform_weight_field_),
      weighted_mode_(weight_field != nullptr),
      weight_scale_(weight_scale > 0.0 ? weight_scale : 1000.0) {}

std::vector<int> MWPMDecoder::decode(const SurfaceSyndrome& syn) {
    std::vector<int> corr(code_.n(), 0);

    if (!syn.sz.empty()) {
        const auto defects = defectsFromPlaquetteSyndrome(syn.sz);
        std::vector<std::pair<int, int>> defect_pairs;
        std::vector<std::pair<int, BoundarySide>> boundary_matches;
        std::vector<int> partner;

        if (!defects.empty()) {
            partner = solveMatchingWithBoundary(defects, true);
            const int k = static_cast<int>(defects.size());
            for (int i = 0; i < k; ++i) {
                const int j = partner[i];
                if (j < 0) continue;
                if (j < k) {
                    if (i < j) {
                        applyPlaquettePairPath(defects[i], defects[j], corr);
                        defect_pairs.emplace_back(i, j);
                    }
                } else if (j == k + i) {
                    BoundarySide side = BoundarySide::LEFT;
                    applyPlaquetteBoundaryPath(defects[i], corr, &side);
                    boundary_matches.emplace_back(i, side);
                } else {
                    std::ostringstream oss;
                    oss << "MWPMDecoder invalid boundary mate mapping for Z-checks: "
                        << "defect_id=" << i << " matched_to=" << j << " expected=" << (k + i);
                    throw std::runtime_error(oss.str());
                }
            }
        }

        if (!syndromeMatches(code_.Hz(), corr, syn.sz)) {
            const std::vector<int> got = code_.Hz().multiply(corr);
            std::ostringstream oss;
            oss << "MWPMDecoder failed to reproduce Z-check syndrome"
                << "\n" << "d=" << d_
                << "\n" << "syndrome_type=Z"
                << "\n" << "defect_coords=" << defectsString(defects)
                << "\n" << "matching_pairs_raw=" << matchingPairsRawString(partner, static_cast<int>(defects.size()))
                << "\n" << "matched_defect_pairs=" << pairsString(defect_pairs, defects)
                << "\n" << "boundary_matches=" << boundaryString(boundary_matches, defects)
                << "\n" << "syndrome_in=" << syndromeString(syn.sz)
                << "\n" << "syndrome_out=" << syndromeString(got);
            throw std::runtime_error(oss.str());
        }
    }

    if (!syn.sx.empty()) {
        const auto defects = defectsFromStarSyndrome(syn.sx);
        std::vector<std::pair<int, int>> defect_pairs;
        std::vector<std::pair<int, BoundarySide>> boundary_matches;
        std::vector<int> partner;

        if (!defects.empty()) {
            partner = solveMatchingWithBoundary(defects, false);
            const int k = static_cast<int>(defects.size());
            for (int i = 0; i < k; ++i) {
                const int j = partner[i];
                if (j < 0) continue;
                if (j < k) {
                    if (i < j) {
                        applyStarPairPath(defects[i], defects[j], corr);
                        defect_pairs.emplace_back(i, j);
                    }
                } else if (j == k + i) {
                    BoundarySide side = BoundarySide::LEFT;
                    applyStarBoundaryPath(defects[i], corr, &side);
                    boundary_matches.emplace_back(i, side);
                } else {
                    std::ostringstream oss;
                    oss << "MWPMDecoder invalid boundary mate mapping for X-checks: "
                        << "defect_id=" << i << " matched_to=" << j << " expected=" << (k + i);
                    throw std::runtime_error(oss.str());
                }
            }
        }

        if (!syndromeMatches(code_.Hx(), corr, syn.sx)) {
            const std::vector<int> got = code_.Hx().multiply(corr);
            std::ostringstream oss;
            oss << "MWPMDecoder failed to reproduce X-check syndrome"
                << "\n" << "d=" << d_
                << "\n" << "syndrome_type=X"
                << "\n" << "defect_coords=" << defectsString(defects)
                << "\n" << "matching_pairs_raw=" << matchingPairsRawString(partner, static_cast<int>(defects.size()))
                << "\n" << "matched_defect_pairs=" << pairsString(defect_pairs, defects)
                << "\n" << "boundary_matches=" << boundaryString(boundary_matches, defects)
                << "\n" << "syndrome_in=" << syndromeString(syn.sx)
                << "\n" << "syndrome_out=" << syndromeString(got);
            throw std::runtime_error(oss.str());
        }
    }

    return corr;
}

int MWPMDecoder::hIndex(int x, int y) const {
    if (x < 0 || x >= d_ - 1 || y < 0 || y >= d_) {
        throw std::out_of_range("MWPMDecoder::hIndex out of range");
    }
    return y * (d_ - 1) + x;
}

int MWPMDecoder::vIndex(int x, int y) const {
    if (x < 0 || x >= d_ || y < 0 || y >= d_ - 1) {
        throw std::out_of_range("MWPMDecoder::vIndex out of range");
    }
    const int h_count = d_ * (d_ - 1);
    return h_count + y * d_ + x;
}

void MWPMDecoder::toggleH(int x, int y, std::vector<int>& corr) const {
    const int q = hIndex(x, y);
    corr[q] ^= 1;
}

void MWPMDecoder::toggleV(int x, int y, std::vector<int>& corr) const {
    const int q = vIndex(x, y);
    corr[q] ^= 1;
}

std::vector<MWPMDecoder::Defect>
MWPMDecoder::defectsFromPlaquetteSyndrome(const std::vector<int>& sz) const {
    if (static_cast<int>(sz.size()) != code_.mz()) {
        throw std::invalid_argument("MWPMDecoder expected sz sized to code.mz()");
    }

    const auto coords = GetZDefects(sz, d_);
    std::vector<Defect> out;
    out.reserve(coords.size());
    for (size_t i = 0; i < coords.size(); ++i) {
        Defect d;
        d.id = static_cast<int>(i);
        d.rc = coords[i];
        d.boundary_flag = false;
        out.push_back(d);
    }
    return out;
}

std::vector<MWPMDecoder::Defect>
MWPMDecoder::defectsFromStarSyndrome(const std::vector<int>& sx) const {
    if (static_cast<int>(sx.size()) != code_.mx()) {
        throw std::invalid_argument("MWPMDecoder expected sx sized to code.mx()");
    }

    const auto coords = GetXDefects(sx, d_);
    std::vector<Defect> out;
    out.reserve(coords.size());
    for (size_t i = 0; i < coords.size(); ++i) {
        Defect d;
        d.id = static_cast<int>(i);
        d.rc = coords[i];
        d.boundary_flag = false;
        out.push_back(d);
    }
    return out;
}

int MWPMDecoder::manhattan(const Defect& a, const Defect& b) const {
    return std::abs(a.rc.c - b.rc.c) + std::abs(a.rc.r - b.rc.r);
}

int MWPMDecoder::weightedCost(const Defect& a, const Defect& b, bool plaquette_mode) const {
    if (!weighted_mode_) return manhattan(a, b);

    const int width = plaquette_mode ? (d_ - 1) : d_;
    auto vertexId = [width](int c, int r) { return r * width + c; };

    const int u = vertexId(a.rc.c, a.rc.r);
    const int v = vertexId(b.rc.c, b.rc.r);
    const double edge_w = std::max(0.0, weight_field_->edge_weight(u, v));
    const double cost = static_cast<double>(manhattan(a, b)) * edge_w;
    return std::max(1, static_cast<int>(std::llround(weight_scale_ * cost)));
}

int MWPMDecoder::DistToBoundaryZ(LatticeCoord zdef, int d) const {
    const int f = d - 1;
    const int left = zdef.c + 1;
    const int right = f - zdef.c;
    const int bottom = zdef.r + 1;
    const int top = f - zdef.r;
    return std::min(std::min(left, right), std::min(bottom, top));
}

int MWPMDecoder::DistToBoundaryX(LatticeCoord xdef, int d) const {
    const int left = xdef.c;
    const int right = (d - 1) - xdef.c;
    const int bottom = xdef.r;
    const int top = (d - 1) - xdef.r;
    return std::min(std::min(left, right), std::min(bottom, top));
}

int MWPMDecoder::boundaryDistance(const Defect& d, bool plaquette_mode) const {
    return plaquette_mode ? DistToBoundaryZ(d.rc, d_) : DistToBoundaryX(d.rc, d_);
}

int MWPMDecoder::weightedBoundaryCost(const Defect& d, bool plaquette_mode) const {
    if (!weighted_mode_) return boundaryDistance(d, plaquette_mode);

    const int width = plaquette_mode ? (d_ - 1) : d_;
    const int u = d.rc.r * width + d.rc.c;
    const double edge_w = std::max(0.0, weight_field_->edge_weight(u, u));
    const double cost = static_cast<double>(boundaryDistance(d, plaquette_mode)) * edge_w;
    return std::max(1, static_cast<int>(std::llround(weight_scale_ * cost)));
}

std::vector<int> MWPMDecoder::solveMatchingWithBoundary(const std::vector<Defect>& defects,
                                                        bool plaquette_mode) const {
    const int k = static_cast<int>(defects.size());
    if (k == 0) return {};

    const int n = 2 * k;
    const int inf = std::numeric_limits<int>::max() / 8;
    std::vector<std::vector<int>> w(n, std::vector<int>(n, inf));
    for (int i = 0; i < n; ++i) w[i][i] = 0;

    for (int i = 0; i < k; ++i) {
        for (int j = i + 1; j < k; ++j) {
            const int wij = weightedCost(defects[i], defects[j], plaquette_mode);
            w[i][j] = wij;
            w[j][i] = wij;
        }

        const int bi = k + i;
        const int wb = weightedBoundaryCost(defects[i], plaquette_mode);
        w[i][bi] = wb;
        w[bi][i] = wb;
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

std::vector<LatticeCoord> MWPMDecoder::PathBetweenDefectsZ(LatticeCoord a, LatticeCoord b, int d) const {
    (void)d;
    std::vector<LatticeCoord> path;
    path.push_back(a);
    while (a.c < b.c) {
        a.c += 1;
        path.push_back(a);
    }
    while (a.c > b.c) {
        a.c -= 1;
        path.push_back(a);
    }
    while (a.r < b.r) {
        a.r += 1;
        path.push_back(a);
    }
    while (a.r > b.r) {
        a.r -= 1;
        path.push_back(a);
    }
    return path;
}

std::vector<LatticeCoord> MWPMDecoder::PathToBoundaryZ(LatticeCoord a,
                                                       int d,
                                                       BoundarySide* chosen_side) const {
    const int f = d - 1;
    const int left = a.c + 1;
    const int right = f - a.c;
    const int bottom = a.r + 1;
    const int top = f - a.r;
    const BoundarySide side = argmin4(left, right, bottom, top);
    if (chosen_side != nullptr) *chosen_side = side;

    std::vector<LatticeCoord> path;
    path.push_back(a);
    switch (side) {
        case BoundarySide::LEFT:
            while (a.c >= 0) {
                a.c -= 1;
                path.push_back(a);
            }
            break;
        case BoundarySide::RIGHT:
            while (a.c < f) {
                a.c += 1;
                path.push_back(a);
            }
            break;
        case BoundarySide::BOTTOM:
            while (a.r >= 0) {
                a.r -= 1;
                path.push_back(a);
            }
            break;
        case BoundarySide::TOP:
            while (a.r < f) {
                a.r += 1;
                path.push_back(a);
            }
            break;
    }
    return path;
}

std::vector<LatticeCoord> MWPMDecoder::PathBetweenDefectsX(LatticeCoord a, LatticeCoord b, int d) const {
    (void)d;
    std::vector<LatticeCoord> path;
    path.push_back(a);
    while (a.c < b.c) {
        a.c += 1;
        path.push_back(a);
    }
    while (a.c > b.c) {
        a.c -= 1;
        path.push_back(a);
    }
    while (a.r < b.r) {
        a.r += 1;
        path.push_back(a);
    }
    while (a.r > b.r) {
        a.r -= 1;
        path.push_back(a);
    }
    return path;
}

std::vector<LatticeCoord> MWPMDecoder::PathToBoundaryX(LatticeCoord a,
                                                       int d,
                                                       BoundarySide* chosen_side) const {
    const int left = a.c;
    const int right = (d - 1) - a.c;
    const int bottom = a.r;
    const int top = (d - 1) - a.r;
    const BoundarySide side = argmin4(left, right, bottom, top);
    if (chosen_side != nullptr) *chosen_side = side;

    std::vector<LatticeCoord> path;
    path.push_back(a);
    switch (side) {
        case BoundarySide::LEFT:
            while (a.c > 0) {
                a.c -= 1;
                path.push_back(a);
            }
            break;
        case BoundarySide::RIGHT:
            while (a.c < d - 1) {
                a.c += 1;
                path.push_back(a);
            }
            break;
        case BoundarySide::BOTTOM:
            while (a.r > 0) {
                a.r -= 1;
                path.push_back(a);
            }
            break;
        case BoundarySide::TOP:
            while (a.r < d - 1) {
                a.r += 1;
                path.push_back(a);
            }
            break;
    }
    return path;
}

void MWPMDecoder::applyPlaquettePairPath(const Defect& a,
                                         const Defect& b,
                                         std::vector<int>& corr) const {
    const auto path = PathBetweenDefectsZ(a.rc, b.rc, d_);
    for (size_t i = 1; i < path.size(); ++i) {
        const LatticeCoord prev = path[i - 1];
        const LatticeCoord next = path[i];
        const int dc = next.c - prev.c;
        const int dr = next.r - prev.r;
        if (dc == 1 && dr == 0) {
            toggleV(prev.c + 1, prev.r, corr);
        } else if (dc == -1 && dr == 0) {
            toggleV(prev.c, prev.r, corr);
        } else if (dc == 0 && dr == 1) {
            toggleH(prev.c, prev.r + 1, corr);
        } else if (dc == 0 && dr == -1) {
            toggleH(prev.c, prev.r, corr);
        }
    }
}

void MWPMDecoder::applyStarPairPath(const Defect& a,
                                    const Defect& b,
                                    std::vector<int>& corr) const {
    const auto path = PathBetweenDefectsX(a.rc, b.rc, d_);
    for (size_t i = 1; i < path.size(); ++i) {
        const LatticeCoord prev = path[i - 1];
        const LatticeCoord next = path[i];
        const int dc = next.c - prev.c;
        const int dr = next.r - prev.r;
        if (dc == 1 && dr == 0) {
            toggleH(prev.c, prev.r, corr);
        } else if (dc == -1 && dr == 0) {
            toggleH(prev.c - 1, prev.r, corr);
        } else if (dc == 0 && dr == 1) {
            toggleV(prev.c, prev.r, corr);
        } else if (dc == 0 && dr == -1) {
            toggleV(prev.c, prev.r - 1, corr);
        }
    }
}

void MWPMDecoder::applyPlaquetteBoundaryPath(const Defect& d,
                                             std::vector<int>& corr,
                                             BoundarySide* chosen_side) const {
    const auto path = PathToBoundaryZ(d.rc, d_, chosen_side);
    for (size_t i = 1; i < path.size(); ++i) {
        const LatticeCoord prev = path[i - 1];
        const LatticeCoord next = path[i];
        const int dc = next.c - prev.c;
        const int dr = next.r - prev.r;
        if (dc == 1 && dr == 0) {
            toggleV(prev.c + 1, prev.r, corr);
        } else if (dc == -1 && dr == 0) {
            toggleV(prev.c, prev.r, corr);
        } else if (dc == 0 && dr == 1) {
            toggleH(prev.c, prev.r + 1, corr);
        } else if (dc == 0 && dr == -1) {
            toggleH(prev.c, prev.r, corr);
        }
    }
}

void MWPMDecoder::applyStarBoundaryPath(const Defect& d,
                                        std::vector<int>& corr,
                                        BoundarySide* chosen_side) const {
    const auto path = PathToBoundaryX(d.rc, d_, chosen_side);
    for (size_t i = 1; i < path.size(); ++i) {
        const LatticeCoord prev = path[i - 1];
        const LatticeCoord next = path[i];
        const int dc = next.c - prev.c;
        const int dr = next.r - prev.r;
        if (dc == 1 && dr == 0) {
            toggleH(prev.c, prev.r, corr);
        } else if (dc == -1 && dr == 0) {
            toggleH(prev.c - 1, prev.r, corr);
        } else if (dc == 0 && dr == 1) {
            toggleV(prev.c, prev.r, corr);
        } else if (dc == 0 && dr == -1) {
            toggleV(prev.c, prev.r - 1, corr);
        }
    }
}

bool MWPMDecoder::syndromeMatches(const BinaryMatrix& H,
                                  const std::vector<int>& corr,
                                  const std::vector<int>& target) const {
    if (target.empty()) return true;
    std::vector<int> syn = H.multiply(corr);
    if (syn.size() != target.size()) return false;
    for (size_t i = 0; i < syn.size(); ++i) {
        if ((syn[i] & 1) != (target[i] & 1)) return false;
    }
    return true;
}
