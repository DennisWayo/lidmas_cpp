#include "surface/MWPMDecoder.h"

#include <algorithm>
#include <cstdlib>
#include <limits>
#include <stdexcept>

namespace {

int argmin4(int a, int b, int c, int d) {
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

} // namespace

MWPMDecoder::MWPMDecoder(const SurfaceCode& code)
    : code_(code),
      d_(code.lattice().distance()) {}

std::vector<int> MWPMDecoder::decode(const SurfaceSyndrome& syn) {
    std::vector<int> corr(code_.n(), 0);

    if (!syn.sz.empty()) {
        const auto defects = defectsFromPlaquetteSyndrome(syn.sz);
        if (!defects.empty()) {
            const auto partner = solveMatchingWithBoundary(defects, true);
            const int k = static_cast<int>(defects.size());
            for (int i = 0; i < k; ++i) {
                const int j = partner[i];
                if (j < 0) continue;
                if (j >= k) {
                    applyPlaquetteBoundaryPath(defects[i], corr);
                } else if (i < j) {
                    applyPlaquettePairPath(defects[i], defects[j], corr);
                }
            }
        }
        if (!syndromeMatches(code_.Hz(), corr, syn.sz)) {
            throw std::runtime_error("MWPMDecoder failed to reproduce Z-check syndrome");
        }
    }

    if (!syn.sx.empty()) {
        const auto defects = defectsFromStarSyndrome(syn.sx);
        if (!defects.empty()) {
            const auto partner = solveMatchingWithBoundary(defects, false);
            const int k = static_cast<int>(defects.size());
            for (int i = 0; i < k; ++i) {
                const int j = partner[i];
                if (j < 0) continue;
                if (j >= k) {
                    applyStarBoundaryPath(defects[i], corr);
                } else if (i < j) {
                    applyStarPairPath(defects[i], defects[j], corr);
                }
            }
        }
        if (!syndromeMatches(code_.Hx(), corr, syn.sx)) {
            throw std::runtime_error("MWPMDecoder failed to reproduce X-check syndrome");
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

    const int f = d_ - 1;
    std::vector<Defect> out;
    for (int r = 0; r < static_cast<int>(sz.size()); ++r) {
        if ((sz[r] & 1) == 0) continue;
        Defect d;
        d.id = static_cast<int>(out.size());
        d.x = r % f;
        d.y = r / f;
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

    std::vector<Defect> out;
    for (int r = 0; r < static_cast<int>(sx.size()); ++r) {
        if ((sx[r] & 1) == 0) continue;
        Defect d;
        d.id = static_cast<int>(out.size());
        d.x = r % d_;
        d.y = r / d_;
        d.boundary_flag = false;
        out.push_back(d);
    }
    return out;
}

int MWPMDecoder::manhattan(const Defect& a, const Defect& b) const {
    return std::abs(a.x - b.x) + std::abs(a.y - b.y);
}

int MWPMDecoder::boundaryDistance(const Defect& d, bool plaquette_mode) const {
    if (plaquette_mode) {
        const int f = d_ - 1;
        const int left = d.x + 1;
        const int right = f - d.x;
        const int bottom = d.y + 1;
        const int top = f - d.y;
        return std::min(std::min(left, right), std::min(bottom, top));
    }

    const int left = d.x;
    const int right = (d_ - 1) - d.x;
    const int bottom = d.y;
    const int top = (d_ - 1) - d.y;
    return std::min(std::min(left, right), std::min(bottom, top));
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
            const int wij = manhattan(defects[i], defects[j]);
            w[i][j] = wij;
            w[j][i] = wij;
        }
        const int bi = k + i;
        const int wb = boundaryDistance(defects[i], plaquette_mode);
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

void MWPMDecoder::applyPlaquettePairPath(const Defect& a,
                                         const Defect& b,
                                         std::vector<int>& corr) const {
    int x = a.x;
    int y = a.y;
    while (x < b.x) {
        toggleV(x + 1, y, corr);
        ++x;
    }
    while (x > b.x) {
        toggleV(x, y, corr);
        --x;
    }
    while (y < b.y) {
        toggleH(x, y + 1, corr);
        ++y;
    }
    while (y > b.y) {
        toggleH(x, y, corr);
        --y;
    }
}

void MWPMDecoder::applyStarPairPath(const Defect& a,
                                    const Defect& b,
                                    std::vector<int>& corr) const {
    int x = a.x;
    int y = a.y;
    while (x < b.x) {
        toggleH(x, y, corr);
        ++x;
    }
    while (x > b.x) {
        toggleH(x - 1, y, corr);
        --x;
    }
    while (y < b.y) {
        toggleV(x, y, corr);
        ++y;
    }
    while (y > b.y) {
        toggleV(x, y - 1, corr);
        --y;
    }
}

void MWPMDecoder::applyPlaquetteBoundaryPath(const Defect& d,
                                             std::vector<int>& corr) const {
    int x = d.x;
    int y = d.y;
    const int f = d_ - 1;

    const int left = x + 1;
    const int right = f - x;
    const int bottom = y + 1;
    const int top = f - y;

    switch (argmin4(left, right, bottom, top)) {
        case 0:
            while (x >= 0) {
                toggleV(x, y, corr);
                --x;
            }
            break;
        case 1:
            while (x < f) {
                toggleV(x + 1, y, corr);
                ++x;
            }
            break;
        case 2:
            while (y >= 0) {
                toggleH(x, y, corr);
                --y;
            }
            break;
        default:
            while (y < f) {
                toggleH(x, y + 1, corr);
                ++y;
            }
            break;
    }
}

void MWPMDecoder::applyStarBoundaryPath(const Defect& d,
                                        std::vector<int>& corr) const {
    int x = d.x;
    int y = d.y;

    const int left = x;
    const int right = (d_ - 1) - x;
    const int bottom = y;
    const int top = (d_ - 1) - y;

    switch (argmin4(left, right, bottom, top)) {
        case 0:
            while (x > 0) {
                toggleH(x - 1, y, corr);
                --x;
            }
            break;
        case 1:
            while (x < d_ - 1) {
                toggleH(x, y, corr);
                ++x;
            }
            break;
        case 2:
            while (y > 0) {
                toggleV(x, y - 1, corr);
                --y;
            }
            break;
        default:
            while (y < d_ - 1) {
                toggleV(x, y, corr);
                ++y;
            }
            break;
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
